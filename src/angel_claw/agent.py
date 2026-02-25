import litellm
import logging
import os
import json
import inspect

logger = logging.getLogger("angel-claw-agent")

# Silence litellm logging to stop the "Give Feedback" messages
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("litellm").setLevel(logging.CRITICAL)

from .models import Message, Role
from .memory import memory_manager
from .config import settings
from .skills.manager import SkillManager
from .mcp_manager import mcp_manager
from typing import List, Optional

class Agent:
    def __init__(self, session_id: str, model: str = None, api_base: str = None):
        self.session_id = session_id
        self.model = model or settings.model
        self.api_base = api_base or settings.api_base
        self.memos = memory_manager.get_memos(session_id)
        # Update memos model and api_base if overridden
        self.memos.reader.model = self.model
        self.memos.reader.api_base = self.api_base
        self.soul = self._load_soul()
        self.history: List[dict] = []
        
        # Initialize Skill Manager
        # Load from both the installed package and the current working directory
        internal_skills = os.path.join(os.path.dirname(__file__), "skills")
        local_skills = os.path.join(os.getcwd(), "skills")
        self.skill_manager = SkillManager([internal_skills, local_skills])

    def _load_soul(self) -> str:
        try:
            with open("SOUL.md", "r") as f:
                return f.read()
        except FileNotFoundError:
            return """# Angel Claw Soul

## Identity
You are Angel Claw, a helpful, intelligent, and empathetic personal AI assistant. You exist to serve the user, 'alice', by remembering important details about their life and preferences.

## Core Beliefs
1.  **Truthfulness**: Always provide accurate information based on your memory. If you don't know something, admit it.
2.  **Helpfulness**: Strive to be as helpful as possible. Anticipate user needs when possible.
3.  **Privacy**: Respect the user's privacy. Only store information that the user explicitly asks you to remember or that is clearly important context for future interactions.
4.  **Empathy**: Understand and respond to the user's emotions. Be supportive and kind.

## Voice and Tone
-   **Professional yet Friendly**: Maintain a professional demeanor but be warm and approachable.
-   **Concise**: Be direct and to the point, avoiding unnecessary fluff.
-   **Encouraging**: Use positive language and encouragement.

## Directives
-   ALWAYS check your memory before answering a question about the user.
-   If you find conflicting information in your memory, ALWAYS prioritize the most recent information. Do not ask for clarification unless the conflict makes it impossible to help.
-   When the user provides new information, acknowledge it briefly and store it directly. NEVER ask for confirmation (e.g., "Is that correct?" or "Would you like me to remember this?")."""

    async def chat(self, user_input: str) -> str:
        # Ensure MCP Manager is connected before chat
        if not mcp_manager.is_connected:
            await mcp_manager.connect()
            
        # 1. Process memory (Retrieval)
        # Use last turn to improve retrieval for short inputs like "yes"
        last_turn = self.history[-1]["content"] if self.history else ""
        retrieval_query = user_input
        if len(user_input.split()) < 3 and last_turn:
            retrieval_query = f"{last_turn} -> {user_input}"
            
        memory_context = self.memos.process(f"Retrieve context for: {retrieval_query}", user="alice")
        
        # 2. Build messages
        system_prompt = (
            f"{self.soul}\n\n"
            f"CURRENT SESSION ID: {self.session_id}\n\n"
            "Use the following memory context to answer. "
            "IMPORTANT: Memories are listed from NEWEST to OLDEST. "
            "If there is conflicting information, ALWAYS trust the NEWEST memory.\n\n"
            "You also have access to 'Skills' which are tools you can call.\n"
            "If you need to perform an action (like creating a skill, listing skills, or searching something), use the appropriate tool.\n\n"
            "IMPORTANT for 'create_skill':\n"
            "1. Do NOT import 'skill' decorator. It is automatically injected into the module's namespace.\n"
            "2. Always use @skill decorator for functions you want to expose as tools.\n"
            "3. Do NOT import any 'angel_claw_sdk' or 'angel_skill_sdk'. They do not exist.\n"
            "4. Use standard Python libraries only, or assume the environment has what you need for basic tasks.\n"
            "5. Example skill code:\n"
            "   @skill\n"
            "   def my_tool(param1: str) -> str:\n"
            "       \"\"\"Description of the tool.\"\"\"\n"
            "       return f'Result: {param1}'\n\n"
            "IMPORTANT for 'schedule_task':\n"
            f"- ALWAYS use the current session ID: '{self.session_id}' unless the user explicitly requests otherwise.\n"
            "- Use 'in' for one-shot relative reminders (e.g., 'remind me in 1 minute' -> kind='in', value='1m').\n"
            "- Use 'every' for recurring tasks (e.g., 'every day' -> kind='every', value='1d').\n"
            "- Seconds ('s'), minutes ('m'), hours ('h'), and days ('d') are all supported.\n\n"
            f"Memory Context:\n{memory_context.get('response', 'No relevant memory found.')}"
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        # Include last 4 turns of history for short-term context
        messages.extend(self.history[-4:])
        messages.append({"role": "user", "content": user_input})
        
        # 3. Call LLM with Tool Support
        assistant_content = ""
        while True:
            # Combine internal skills and MCP tools
            tools = self.skill_manager.get_tool_definitions()
            mcp_tools = await mcp_manager.get_tool_definitions()
            all_tools = tools + mcp_tools
            
            try:
                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    api_key=settings.api_key,
                    api_base=self.api_base,
                    tools=all_tools if all_tools else None,
                    tool_choice="auto" if all_tools else None
                )
            except Exception as e:
                # Handle common errors with friendly messages
                error_msg = str(e)
                if "401" in error_msg or "authentication" in error_msg.lower():
                    return "❌ LLM Authentication Error: Your API key seems invalid. Run 'angel-claw chat --reconfigure' to update it."
                elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
                    return "❌ LLM Quota Error: You have exceeded your API quota. Please check your provider dashboard."
                elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                    return f"❌ LLM Model Error: Model '{self.model}' not found. Run 'angel-claw chat --reconfigure' to change it."
                return f"❌ LLM Error: {e}"
            
            message = response.choices[0].message
            # litellm returns a message object that we need to convert to dict for history if it has tool_calls
            msg_dict = {"role": "assistant", "content": message.content}
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            
            messages.append(msg_dict)
            
            if not message.tool_calls:
                assistant_content = message.content or ""
                break
                
            # Handle Tool Calls
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}
                
                if function_name in self.skill_manager.skills:
                    function_to_call = self.skill_manager.skills[function_name]
                    # Automatically inject current session_id into schedule_task to ensure correct routing
                    if function_name == "schedule_task":
                        function_args["session_id"] = self.session_id
                        
                    try:
                        logger.info(f"⚙️ [Skill] {function_name}({function_args})")
                        if inspect.iscoroutinefunction(function_to_call):
                            function_result = await function_to_call(**function_args)
                        else:
                            function_result = function_to_call(**function_args)
                    except Exception as e:
                        logger.error(f"❌ [Error] skill {function_name}: {e}")
                        function_result = f"Error executing {function_name}: {e}"
                elif function_name in mcp_manager.tool_to_server:
                    logger.info(f"⚙️ [MCP] {function_name}({function_args})")
                    function_result = await mcp_manager.call_tool(function_name, function_args)
                else:
                    function_result = f"Error: Skill or MCP tool '{function_name}' not found."
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": str(function_result),
                })
            
            # Refresh skills in case a new one was created/installed
            self.skill_manager.load_skills()
        
        # 4. Update short-term history
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": assistant_content})
        
        # 5. Store interaction in memory
        # Let the memory system parse the user input to see if it's a fact to store
        mem_res = self.memos.process(user_input, user="alice")
        
        # If the memory system didn't identify this as a storage/update operation,
        # we store the full dialogue turn as context for future retrieval.
        if mem_res.get("parsed", {}).get("operation") not in ["store", "update"]:
             self.memos.process(f"Remember: User said '{user_input}' and Assistant replied '{assistant_content}'", user="alice")
        
        return assistant_content
