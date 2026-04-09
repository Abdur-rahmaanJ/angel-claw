import logging
import re
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any

import litellm
from .app_context import create_app_context_manager
from .credits import create_credit_service
from .history import create_history_service
from .memory import create_memory_service
from .todos import create_todo_service
from .api_keys import create_api_key_service
from .pairing import create_pairing_service
from .config import MAX_RECURSION_DEPTH
from .message_builder import create_message_builder, create_memory_retriever
from .executor import create_llm_executor
from ..models import Message, Role, UserContext, EngineResponse, Todo
from ..config import settings

logger = logging.getLogger("angel-claw-engine")

litellm.suppress_debug_info = True
litellm.add_disable_loading_cost_map = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)


class AngelClawEngine:
    def __init__(self):
        self._app_context_manager = create_app_context_manager(settings)
        self._credit_service = create_credit_service(settings)
        self._history_service = create_history_service()
        self._memory_service = create_memory_service()
        self._todo_service = create_todo_service()
        self._api_key_service = create_api_key_service(
            settings, self._app_context_manager
        )
        self._pairing_service = create_pairing_service(
            settings, self._app_context_manager
        )
        self._message_builder = create_message_builder(settings)
        self._memory_retriever = create_memory_retriever()
        self._llm_executor = create_llm_executor(settings)

    def set_app(self, app):
        self._app_context_manager.set_app(app)

    def user_root(self, user_id: str) -> Path:
        from angel_claw.utils import get_user_root

        return get_user_root(user_id)

    def _ensure_channel(self, context: UserContext):
        if settings.auth_mode == "shopyo":
            with self._app_context_manager._app_context():
                try:
                    from modules.agent.models import Channel
                    from init import db

                    channel = Channel.query.filter_by(
                        channel_type=context.channel_type,
                        channel_identifier=context.channel_identifier,
                    ).first()

                    if not channel:
                        channel = Channel(
                            user_id=context.user_id,
                            channel_type=context.channel_type,
                            channel_identifier=context.channel_identifier,
                            is_active=True,
                        )
                        db.session.add(channel)
                    else:
                        channel.last_seen_at = datetime.now(UTC)
                        channel.user_id = context.user_id
                        channel.is_active = True

                    db.session.commit()
                except Exception as e:
                    logger.error(f"Error ensuring channel: {e}")

    async def execute(
        self, context: UserContext, message: str, use_global: bool = False
    ) -> EngineResponse:
        with self._app_context_manager._app_context() as ctx:
            if ctx:
                return await self._execute_internal(
                    context, message, use_global=use_global
                )
        return await self._execute_internal(context, message, use_global=use_global)

    async def _execute_internal(
        self, context: UserContext, message: str, use_global: bool = False
    ) -> EngineResponse:
        from angel_claw.runtime.manager import runtime_manager
        from angel_claw.chat_logger import chat_logger
        from angel_claw.runtime.cache import cache

        self._ensure_channel(context)
        session_id = context.channel_identifier
        user_id = context.user_id

        runtime = await runtime_manager.get_runtime(context)
        runtime.add_message(session_id, Message(role=Role.USER, content=message))

        await runtime_manager.start_cleanup_task()

        allowed, err_msg = await self._credit_service.check_credits(
            user_id, "chat_message"
        )
        if not allowed:
            return EngineResponse(content=err_msg)

        runtime = await runtime_manager.get_runtime(context)
        memos = runtime.get_memos(session_id)
        history = await runtime.chat_history(session_id)

        recent_history = history[-5:] if len(history) > 5 else history

        retrieved_cubes = self._memory_retriever.retrieve(
            memos, context, session_id, use_global
        )
        raw_memory = self._memory_retriever.format_memory_context(
            retrieved_cubes, memos
        )
        safe_memory = self._memory_retriever.sanitize_memory(raw_memory)

        current_depth = self._message_builder.extract_recursion_depth(message)
        if current_depth > MAX_RECURSION_DEPTH:
            logger.warning(
                f"Max recursion depth reached ({MAX_RECURSION_DEPTH}) for user {user_id}"
            )
            return EngineResponse(
                content="[SYSTEM: Maximum recursive workflow depth reached. Execution halted to prevent infinite loops.]"
            )

        system_prompt = self._message_builder.build_system_prompt(
            runtime, context, user_id, safe_memory
        )
        messages = self._message_builder.build_messages(
            system_prompt, recent_history, message
        )

        model = runtime.vault.get("MODEL", settings.model)
        api_base = runtime.vault.get("MODEL_BASE_URL", settings.api_base)
        api_key = runtime.vault.get("MODEL_KEY", settings.api_key)

        all_tools = await runtime.get_tool_definitions()

        (
            assistant_content,
            tool_calls_list,
            total_tokens,
        ) = await self._llm_executor.execute_with_tools(
            model=model,
            messages=messages,
            all_tools=all_tools,
            api_key=api_key,
            api_base=api_base,
            runtime=runtime,
            session_id=session_id,
            user_id=user_id,
            credit_service=self._credit_service,
        )

        runtime.add_message(
            session_id, Message(role=Role.ASSISTANT, content=assistant_content)
        )

        mem_res = memos.process(
            message,
            user=context.email,
            response=assistant_content,
            namespace=session_id,
        )

        chat_logger.log(user_id, session_id, message, assistant_content)

        credit_amount = self._credit_service.calculate_token_cost(total_tokens)
        self._credit_service.deduct_credits(
            user_id,
            "chat_message",
            {"session_id": session_id, "tokens": total_tokens},
            amount=credit_amount,
        )

        return EngineResponse(
            content=assistant_content,
            tool_calls=tool_calls_list if tool_calls_list else None,
        )

    async def execute_streaming(
        self, context: UserContext, message: str, use_global: bool = False
    ):
        from flask import has_app_context

        in_app_context = has_app_context()

        if in_app_context:
            async for chunk in self._execute_streaming_internal(
                context, message, use_global=use_global
            ):
                yield chunk
        else:
            with self._app_context_manager._app_context() as ctx:
                if ctx:
                    async for chunk in self._execute_streaming_internal(
                        context, message, use_global=use_global
                    ):
                        yield chunk
                else:
                    async for chunk in self._execute_streaming_internal(
                        context, message, use_global=use_global
                    ):
                        yield chunk

    async def _execute_streaming_internal(
        self, context: UserContext, message: str, use_global: bool = False
    ):
        from angel_claw.runtime.manager import runtime_manager
        from angel_claw.runtime.cache import cache

        self._ensure_channel(context)
        session_id = context.channel_identifier
        user_id = context.user_id

        runtime = await runtime_manager.get_runtime(context)
        runtime.add_message(session_id, Message(role=Role.USER, content=message))

        await runtime_manager.start_cleanup_task()

        allowed, err_msg = await self._credit_service.check_credits(
            user_id, "chat_message"
        )
        if not allowed:
            yield err_msg
            return

        runtime = await runtime_manager.get_runtime(context)
        memos = runtime.get_memos(session_id)
        history = await runtime.chat_history(session_id)

        recent_history = history[-5:] if len(history) > 5 else history

        retrieved_cubes = self._memory_retriever.retrieve(
            memos, context, session_id, use_global
        )
        raw_memory = self._memory_retriever.format_memory_context(
            retrieved_cubes, memos
        )
        safe_memory = self._memory_retriever.sanitize_memory(raw_memory)

        system_prompt = self._message_builder.build_streaming_system_prompt(
            runtime, context, user_id, safe_memory
        )

        messages = [{"role": "system", "content": system_prompt}]
        for msg in recent_history:
            if msg.role.value == "system":
                continue
            messages.append({"role": msg.role.value, "content": msg.content})
        messages.append({"role": "user", "content": message})

        model = settings.model
        api_key = settings.api_key
        api_base = settings.api_base

        all_tools = await runtime.skills.get_tool_definitions()

        async for char in self._llm_executor.execute_streaming(
            model=model,
            messages=messages,
            all_tools=all_tools,
            api_key=api_key,
            api_base=api_base,
            runtime=runtime,
            session_id=session_id,
            user_id=user_id,
            credit_service=self._credit_service,
        ):
            yield char

        runtime.add_message(session_id, Message(role=Role.ASSISTANT, content=""))
        memos.process(
            message,
            user=context.email,
            response="",
            namespace=session_id,
        )

    def get_history(self, context: UserContext) -> List[Message]:
        return self._history_service.get_history(
            context.user_id, context.channel_identifier
        )

    def get_chat_sessions(self, context: UserContext) -> List[Dict[str, str]]:
        return self._history_service.get_sessions(context)

    def delete_chat_session(self, context: UserContext, session_id: str):
        self._history_service.delete_session(context, session_id)

    def rename_chat_session(self, context: UserContext, old_id: str, new_name: str):
        self._history_service.rename_session(context, old_id, new_name)

    def get_memories(self, context: UserContext) -> List[Dict[str, Any]]:
        return self._memory_service.get_memories(context)

    def delete_memory(self, context: UserContext, memory_id: str):
        self._memory_service.delete_memory(context, memory_id)

    def list_todos(self, context: UserContext) -> List[Todo]:
        return self._todo_service.list_todos(context)

    def create_api_key(self, context: UserContext, name: str) -> str:
        return self._api_key_service.create_api_key(context, name)

    def revoke_api_key(self, context: UserContext, key_id: str):
        self._api_key_service.revoke_api_key(context, key_id)

    def pair_channel(self, context: UserContext, channel_type: str, identifier: str):
        self._pairing_service.pair_channel(context, channel_type, identifier)

    def generate_pair_token(self, context: UserContext) -> str:
        return self._pairing_service.generate_pair_token(context)

    def validate_pair_token(self, token: str) -> Optional[str]:
        return self._pairing_service.validate_pair_token(token)

    def validate_api_key(self, raw_key: str) -> Optional[UserContext]:
        return self._api_key_service.validate_api_key(raw_key)
