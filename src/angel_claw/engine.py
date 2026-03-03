import litellm
import logging
import os
import json
import inspect
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import Message, Role, UserContext, EngineResponse, Todo
from .memory import memory_manager
from .config import settings
from .skills.manager import SkillManager
from .mcp_manager import mcp_manager
from .chat_logger import chat_logger
from .skills.todo import _load_todos

from .utils import get_user_root

logger = logging.getLogger("angel-claw-engine")

# Silence litellm logging
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("litellm").setLevel(logging.CRITICAL)

class AngelClawEngine:
    def __init__(self):
        # Global skill manager (can be shared or instantiated per user if isolation requires custom skills)
        internal_skills = os.path.join(os.path.dirname(__file__), "skills")
        local_skills = os.path.join(os.getcwd(), "skills")
        self.skill_manager = SkillManager([internal_skills, local_skills])
        self.soul = self._load_soul()
        # In-memory history for now, should eventually be persisted in DB or user-specific files
        self._histories: Dict[str, List[Message]] = {}

    def _load_soul(self) -> str:
        try:
            with open("SOUL.md", "r") as f:
                return f.read()
        except FileNotFoundError:
            return "# Angel Claw Soul\nDefault soul content..."

    def _get_user_history(self, user_id: str, session_id: str) -> List[Message]:
        key = f"{user_id}:{session_id}"
        if key not in self._histories:
            self._histories[key] = []
        return self._histories[key]
    
    def user_root(self, user_id: str) -> Path:
        return get_user_root(user_id)

    def _ensure_channel(self, context: UserContext):
        if settings.auth_mode == "shopyo":
            try:
                # Use absolute imports for Shopyo environment
                from modules.agent.models import Channel
                from init import db
                
                channel = Channel.query.filter_by(
                    channel_type=context.channel_type,
                    channel_identifier=context.channel_identifier
                ).first()
                
                if not channel:
                    channel = Channel(
                        user_id=context.user_id,
                        channel_type=context.channel_type,
                        channel_identifier=context.channel_identifier
                    )
                    db.session.add(channel)
                else:
                    channel.last_seen_at = datetime.utcnow()
                    channel.user_id = context.user_id 
                
                db.session.commit()
            except ImportError:
                logger.warning("Could not import Shopyo models, skipping channel sync")
            except Exception as e:
                logger.error(f"Error ensuring channel: {e}")

    async def execute(self, context: UserContext, message: str) -> EngineResponse:
        # Ensure channel record exists
        self._ensure_channel(context)
        
        # Ensure MCP Manager is connected
        if not mcp_manager.is_connected:
            await mcp_manager.connect()

        session_id = context.channel_identifier # For web, this could be session_id
        user_id = context.user_id
        
        memos = memory_manager.get_memos(user_id, session_id)
        history = self._get_user_history(user_id, session_id)

        # 1. Retrieval
        last_turn = history[-1].content if history else ""
        retrieval_query = message
        if len(message.split()) < 3 and last_turn:
            retrieval_query = f"{last_turn} -> {message}"

        recent_history = history[-4:] if len(history) >= 4 else history
        
        memory_context = memos.process(
            f"Retrieve context for: {retrieval_query}", user=context.email
        )

        # 2. Build messages
        system_prompt = (
            f"{self.soul}\n\n"
            f"CURRENT USER: {context.email} (ID: {user_id})\n"
            f"CHANNEL: {context.channel_type} ({context.channel_identifier})\n\n"
            "Use the following memory context to answer. "
            "IMPORTANT: Memories are listed from NEWEST to OLDEST. "
            "If there is conflicting information, ALWAYS trust the NEWEST memory.\n\n"
            "You also have access to 'Skills' which are tools you can call.\n"
            f"Memory Context:\n{memory_context.get('response', 'No relevant memory found.')}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        # Convert Message objects to dicts for litellm
        messages.extend([m.model_dump(exclude_none=True) for m in recent_history])
        messages.append({"role": "user", "content": message})

        # 3. Call LLM
        assistant_content = ""
        tool_calls_list = []
        
        while True:
            tools = self.skill_manager.get_tool_definitions()
            mcp_tools = await mcp_manager.get_tool_definitions()
            all_tools = tools + mcp_tools

            response = await litellm.acompletion(
                model=settings.model,
                messages=messages,
                api_key=settings.api_key,
                api_base=settings.api_base,
                tools=all_tools if all_tools else None,
                tool_choice="auto" if all_tools else None,
            )

            response_message = response.choices[0].message
            msg_dict = {"role": "assistant", "content": response_message.content}
            
            if response_message.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in response_message.tool_calls
                ]
                tool_calls_list.extend(msg_dict["tool_calls"])

            messages.append(msg_dict)

            if not response_message.tool_calls:
                assistant_content = response_message.content or ""
                break

            # Handle Tool Calls
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}

                if function_name in self.skill_manager.skills:
                    function_to_call = self.skill_manager.skills[function_name]
                    # Inject context-specific data if needed
                    # We pass session_id as channel_identifier for now to maintain compat with existing skills
                    sig = inspect.signature(function_to_call)
                    if "session_id" in sig.parameters:
                         if "session_id" not in function_args:
                             function_args["session_id"] = session_id
                    
                    if "user_id" in sig.parameters:
                         if "user_id" not in function_args:
                             function_args["user_id"] = user_id


                    try:
                        if inspect.iscoroutinefunction(function_to_call):
                            function_result = await function_to_call(**function_args)
                        else:
                            function_result = function_to_call(**function_args)
                    except Exception as e:
                        function_result = f"Error executing {function_name}: {e}"
                elif function_name in mcp_manager.tool_to_server:
                    function_result = await mcp_manager.call_tool(
                        function_name, function_args
                    )
                else:
                    function_result = f"Error: Tool '{function_name}' not found."

                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_result),
                    }
                )

        # 4. Update history
        history.append(Message(role=Role.USER, content=message))
        history.append(Message(role=Role.ASSISTANT, content=assistant_content))

        # 5. Store in memory
        mem_res = memos.process(message, user=context.email)
        if mem_res.get("parsed", {}).get("operation") not in ["store", "update"]:
            memos.process(
                f"Remember: User said '{message}' and Assistant replied '{assistant_content}'",
                user=context.email,
            )

        # Log chat
        chat_logger.log(f"{user_id}:{session_id}", message, assistant_content)

        return EngineResponse(content=assistant_content, tool_calls=tool_calls_list if tool_calls_list else None)

    def get_history(self, context: UserContext) -> List[Message]:
        return self._get_user_history(context.user_id, context.channel_identifier)

    def list_todos(self, context: UserContext) -> List[Todo]:
        # Currently using _load_todos which expects session_id. 
        # Using channel_identifier as session_id for now, but passing user_id for isolation.
        todos_data = _load_todos(context.channel_identifier, user_id=context.user_id)

        todos = []
        for t in todos_data:
            todos.append(Todo(
                id=str(t.get("id")),
                content=t.get("content"),
                completed=t.get("completed", False),
                priority=t.get("priority", "medium"),
                due_date=t.get("due_date"),
                created_at=t.get("created_at"),
                completed_at=t.get("completed_at")
            ))
        return todos

    def create_api_key(self, context: UserContext, name: str) -> str:
        if settings.auth_mode == "shopyo":
            import secrets
            import hashlib
            from modules.agent.models import ApiKey
            from init import db
            
            # Generate key: ac_v1_{prefix}_{random}
            prefix = secrets.token_hex(4) # 8 chars
            random_part = secrets.token_urlsafe(32)
            raw_key = f"ac_v1_{prefix}_{random_part}"
            
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            
            api_key = ApiKey(
                user_id=context.user_id,
                name=name,
                key_hash=key_hash,
                prefix=prefix
            )
            db.session.add(api_key)
            db.session.commit()
            return raw_key
        else:
            raise NotImplementedError("API Key creation only supported in Shopyo mode for now")

    def revoke_api_key(self, context: UserContext, key_id: str) -> None:
        if settings.auth_mode == "shopyo":
            from modules.agent.models import ApiKey
            from init import db
            
            api_key = ApiKey.query.filter_by(id=key_id, user_id=context.user_id).first()
            if api_key:
                api_key.is_active = False
                db.session.commit()
        else:
            raise NotImplementedError("API Key revocation only supported in Shopyo mode for now")

    def pair_channel(self, context: UserContext, channel_type: str, identifier: str):
        if settings.auth_mode == "shopyo":
            from modules.agent.models import Channel
            from init import db
            
            channel = Channel.query.filter_by(
                channel_type=channel_type,
                channel_identifier=identifier
            ).first()
            
            if not channel:
                channel = Channel(
                    user_id=context.user_id,
                    channel_type=channel_type,
                    channel_identifier=identifier
                )
                db.session.add(channel)
            else:
                channel.user_id = context.user_id
                channel.last_seen_at = datetime.utcnow()
            
            db.session.commit()
        else:
            raise NotImplementedError("Channel pairing only supported in Shopyo mode for now")

    def generate_pair_token(self, context: UserContext) -> str:
        if settings.auth_mode == "shopyo":
            import secrets
            from datetime import timedelta
            from modules.agent.models import PairingToken
            from init import db
            
            token = secrets.token_urlsafe(16)
            pairing_token = PairingToken(
                token=token,
                user_id=context.user_id,
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            )
            db.session.add(pairing_token)
            db.session.commit()
            return token
        else:
            raise NotImplementedError("Pairing token generation only supported in Shopyo mode for now")

    def validate_pair_token(self, token: str) -> Optional[str]:
        """Validates a pairing token and returns the user_id if valid."""
        if settings.auth_mode == "shopyo":
            from modules.agent.models import PairingToken
            from init import db
            
            pairing_token = PairingToken.query.filter_by(
                token=token,
                consumed=False
            ).first()
            
            if pairing_token and pairing_token.expires_at > datetime.utcnow():
                pairing_token.consumed = True
                db.session.commit()
                return pairing_token.user_id
            return None
        else:
            raise NotImplementedError("Pairing token validation only supported in Shopyo mode for now")


    def validate_api_key(self, raw_key: str) -> Optional[UserContext]:
        if settings.auth_mode == "shopyo":
            import hashlib
            from modules.agent.models import ApiKey
            from shopyo_auth.models import User
            
            # Extract prefix: ac_v1_{prefix}_{random}
            parts = raw_key.split("_")
            if len(parts) < 4:
                return None
            prefix = parts[2]
            
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            
            api_key = ApiKey.query.filter_by(
                prefix=prefix,
                key_hash=key_hash,
                is_active=True
            ).first()
            
            if api_key:
                user = User.query.get(api_key.user_id)
                if user:
                    api_key.last_used_at = datetime.utcnow()
                    from init import db
                    db.session.commit()
                    
                    return UserContext(
                        user_id=str(user.id),
                        email=user.email,
                        roles=[r.name for r in user.roles] if hasattr(user, "roles") else [],
                        channel_type="api",
                        channel_identifier="api-key"
                    )
            return None
        else:
            raise NotImplementedError("API Key validation only supported in Shopyo mode for now")
