from angel_recall import MemOS
from .config import settings
import os

class MemoryManager:
    def __init__(self):
        if not os.path.exists(settings.memory_persist_dir):
            os.makedirs(settings.memory_persist_dir)
            
    def get_memos(self, session_id: str) -> MemOS:
        persist_dir = os.path.join(settings.memory_persist_dir, session_id)
        return MemOS(
            persist_directory=persist_dir, 
            model=settings.model,
            api_base=settings.api_base
        )

memory_manager = MemoryManager()
