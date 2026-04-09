import logging
from typing import List, Dict, Any, Protocol
from ..models import UserContext

logger = logging.getLogger("angel-claw-engine-memory")


class MemoryServiceProtocol(Protocol):
    """Protocol for memory service - enables dependency injection."""

    def get_memories(self, context: UserContext) -> List[Dict[str, Any]]: ...

    def delete_memory(self, context: UserContext, memory_id: str): ...


class MemoryService:
    """Memory service for managing user memories with DI support."""

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

    def get_memories(self, context: UserContext) -> List[Dict[str, Any]]:
        """Get all memories for a user across all namespaces."""
        from asgiref.sync import async_to_sync

        runtime = async_to_sync(self._get_runtime_manager().get_runtime)(context)
        memos = runtime.get_memos(context.channel_identifier)

        all_memories = []
        for namespace, ids in memos.vault.namespaces.items():
            for cid in ids:
                cube = memos.vault.get(cid)
                if cube and cube.owner == context.email:
                    all_memories.append(cube.to_dict())

        return all_memories

    def delete_memory(self, context: UserContext, memory_id: str):
        """Delete a specific memory by ID."""
        from asgiref.sync import async_to_sync

        runtime = async_to_sync(self._get_runtime_manager().get_runtime)(context)
        memos = runtime.get_memos(context.channel_identifier)
        memos.vault.delete(memory_id)


def create_memory_service(runtime_manager=None) -> MemoryService:
    """Factory function to create a MemoryService."""
    return MemoryService(runtime_manager)
