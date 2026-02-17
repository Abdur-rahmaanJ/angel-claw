from angel_recall import MemOS
from .config import settings
import os

class MemoryManager:
    def __init__(self):
        if not os.path.exists(settings.memory_persist_dir):
            os.makedirs(settings.memory_persist_dir)
            
    def get_memos(self, session_id: str) -> MemOS:
        # For CLI, we use a fixed 'default' vault to ensure long-term memory across sessions
        persist_dir = os.path.join(settings.memory_persist_dir, "default")
        return MemOS(persist_directory=persist_dir, model=settings.model)

memory_manager = MemoryManager()
