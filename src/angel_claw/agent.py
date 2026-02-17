import litellm
import logging

# Silence litellm logging to stop the "Give Feedback" messages
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

from .models import Message, Role
from .memory import memory_manager
from .config import settings
from typing import List, Optional

class Agent:
    def __init__(self, session_id: str, model: str = None):
        self.session_id = session_id
        self.model = model or settings.model
        self.memos = memory_manager.get_memos(session_id)
        # Update memos model if overridden
        self.memos.reader.model = self.model
        self.soul = self._load_soul()
        self.history: List[dict] = []

    def _load_soul(self) -> str:
        try:
            with open("SOUL.md", "r") as f:
                return f.read()
        except FileNotFoundError:
            return "You are Angel Claw, a helpful personal AI assistant."

    async def chat(self, user_input: str) -> str:
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
            "Use the following memory context to answer. "
            "IMPORTANT: Memories are listed from NEWEST to OLDEST. "
            "If there is conflicting information, ALWAYS trust the NEWEST memory.\n\n"
            f"Memory Context:\n{memory_context.get('response', 'No relevant memory found.')}"
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        # Include last 4 turns of history for short-term context
        messages.extend(self.history[-4:])
        messages.append({"role": "user", "content": user_input})
        
        # 3. Call LLM via litellm
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            api_key=settings.api_key
        )
        
        assistant_content = response.choices[0].message.content
        
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
