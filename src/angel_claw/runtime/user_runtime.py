import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models import Message, UserContext, EngineResponse
from ..memory import memory_manager
from .persistence import PersistentHistory, UserVault
from .registry import TieredSkillRegistry
from ..lane_queue.queue import lane_queue
from ..lane_queue.task import Task
from ..config import settings

logger = logging.getLogger("angel-claw-runtime")


class FairShareScheduler:
    """Isolated scheduler for a single user."""

    def __init__(self, context: UserContext):
        self.context = context
        self.lane_key = f"user_{context.user_id}"

    async def schedule(self, task_id: str, execute_func, data=None):
        task = Task(
            task_id=task_id,
            lane_key=self.lane_key,
            execute_func=execute_func,
            data=data,
        )
        return await lane_queue.enqueue(task)


class UserRuntime:
    """Isolated runtime for a single user."""

    def __init__(self, context: UserContext):
        self.context = context
        self.history = PersistentHistory(context)
        self.vault = UserVault(context)
        self.skills = TieredSkillRegistry(context)
        self.scheduler = FairShareScheduler(context)

        # Soul Hierarchy: User SOUL.md > Global SOUL.md
        self.soul = self._load_soul()

        # Last active timestamp for LRU
        from datetime import datetime, UTC

        self.last_active = datetime.now(UTC)

    def _load_soul(self) -> str:
        from ..utils import get_user_root

        user_root = get_user_root(self.context.user_id)
        user_soul = user_root / "SOUL.md"

        if user_soul.exists():
            with open(user_soul, "r") as f:
                return f.read()

        # Fallback to global SOUL.md in project root
        import os

        project_root = Path(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ).parent
        search_paths = [
            project_root / "SOUL.md",
        ]

        for path in search_paths:
            if path.exists():
                with open(path, "r") as f:
                    return f.read()

        return "# Angel Claw Soul\nDefault soul content..."

    def update_soul(self, content: str):
        from ..utils import get_user_root

        user_root = get_user_root(self.context.user_id)
        user_soul = user_root / "SOUL.md"
        with open(user_soul, "w") as f:
            f.write(content)
        self.soul = content

    def get_soul_templates(self) -> Dict[str, str]:
        return {
            "Default": "# Angel Claw Soul\nYou are a helpful AI assistant...",
            "Life Coach": "# Life Coach Soul\nYou are an empathetic and motivating life coach. You help the user set goals, stay accountable, and maintain a positive mindset.",
            "Developer": "# Developer Soul\nYou are a senior software engineer. You provide technical, concise, and efficient solutions. You always consider edge cases and security.",
            "Creative Writer": "# Creative Writer Soul\nYou are a brilliant storyteller and poet. Your language is descriptive and evocative. You help the user brainstorm and refine creative ideas.",
            "Personal Assistant": "# Personal Assistant Soul\nYou are a highly organized executive assistant. You focus on efficiency, scheduling, and ensuring no detail is missed.",
        }

    def apply_soul_template(self, template_name: str):
        templates = self.get_soul_templates()
        if template_name in templates:
            self.update_soul(templates[template_name])
            return True
        return False

    def mark_active(self):
        from datetime import datetime, UTC

        self.last_active = datetime.now(UTC)

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return await self.skills.get_tool_definitions()

    async def call_tool(
        self, name: str, arguments: Dict[str, Any], session_id: str
    ) -> str:
        return await self.skills.call_tool(name, arguments, session_id)

    def get_memos(self, session_id: str):
        # Delegate to memory manager but with user isolation
        return memory_manager.get_memos(self.context.user_id, session_id)

    async def chat_history(self, session_id: str) -> List[Message]:
        return self.history.get_history(session_id)

    def add_message(self, session_id: str, message: Message):
        self.history.add_message(session_id, message)
