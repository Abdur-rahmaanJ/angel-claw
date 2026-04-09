import logging
from typing import List, Dict, Any, Protocol
from ..models import UserContext, Message

logger = logging.getLogger("angel-claw-engine-history")


class HistoryServiceProtocol(Protocol):
    """Protocol for history service - enables dependency injection."""

    def get_history(self, user_id: str, session_id: str) -> List[Message]: ...

    async def get_history_async(
        self, user_id: str, session_id: str
    ) -> List[Message]: ...

    def get_sessions(self, context: UserContext) -> List[Dict[str, str]]: ...

    def delete_session(self, context: UserContext, session_id: str): ...

    def rename_session(self, context: UserContext, old_id: str, new_name: str): ...


class HistoryService:
    """History service wrapping PersistentHistory with DI support."""

    def __init__(self, runtime_manager=None):
        """
        Args:
            runtime_manager: Runtime manager instance. If None, imports from angel_claw.runtime.manager.
        """
        self._runtime_manager = runtime_manager

    def _get_runtime_manager(self):
        if self._runtime_manager:
            return self._runtime_manager
        from angel_claw.runtime.manager import runtime_manager

        return runtime_manager

    def _create_persistent_history(self, context: UserContext):
        from angel_claw.runtime.persistence import PersistentHistory

        return PersistentHistory(context)

    def get_history(self, user_id: str, session_id: str) -> List[Message]:
        """Get chat history for a session (sync version)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return self._get_history_sync(user_id, session_id)
            else:
                return loop.run_until_complete(
                    self._get_history_async(user_id, session_id)
                )
        except Exception:
            return self._get_history_sync(user_id, session_id)

    def _get_history_sync(self, user_id: str, session_id: str) -> List[Message]:
        from angel_claw.runtime.persistence import PersistentHistory
        from ..models import UserContext

        context = UserContext(
            user_id=user_id,
            email="",
            roles=[],
            channel_type="",
            channel_identifier="",
        )
        history = PersistentHistory(context)
        return history.get_history(session_id)

    async def get_history_async(self, user_id: str, session_id: str) -> List[Message]:
        """Get chat history for a session (async version)."""
        from ..models import UserContext

        context = UserContext(
            user_id=user_id, email="", roles=[], channel_type="", channel_identifier=""
        )
        runtime = await self._get_runtime_manager().get_runtime(context)
        return await runtime.chat_history(session_id)

    def get_sessions(self, context: UserContext) -> List[Dict[str, str]]:
        """Get all chat sessions for a user."""
        history = self._create_persistent_history(context)
        return history.get_sessions()

    def delete_session(self, context: UserContext, session_id: str):
        """Delete a chat session."""
        history = self._create_persistent_history(context)
        history.delete_session(session_id)

    def rename_session(self, context: UserContext, old_id: str, new_name: str):
        """Rename a chat session."""
        history = self._create_persistent_history(context)
        history.rename_session(old_id, new_name)


def create_history_service(runtime_manager=None) -> HistoryService:
    """Factory function to create a HistoryService."""
    return HistoryService(runtime_manager)
