from angel_recall import MemOS
from .config import settings
from .utils import get_user_root
import os

class MemoryManager:
    def __init__(self):
        # We don't strictly need to create settings.memory_persist_dir anymore
        # as we are using get_user_root, but we keep it for now if needed.
        if not os.path.exists(settings.memory_persist_dir):
            os.makedirs(settings.memory_persist_dir)
            
    def get_memos(self, user_id: str, session_id: str) -> MemOS:
        # Use user-isolated paths as per plan: ~/.angelclaw/users/{user_id}/memory/{session_id}
        user_root = get_user_root(user_id)
        persist_dir = user_root / "memory" / session_id
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        return MemOS(
            persist_directory=str(persist_dir), 
            model=settings.model,
            api_base=settings.api_base
        )

memory_manager = MemoryManager()
