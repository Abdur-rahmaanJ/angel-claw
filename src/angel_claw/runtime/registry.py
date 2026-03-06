import os
import logging
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Callable, Optional
from ..skills.manager import SkillManager
from ..models import UserContext

logger = logging.getLogger("angel-claw-registry")

class TieredSkillRegistry:
    """Manages global and user-specific skills with execution sandboxing."""
    def __init__(self, context: UserContext):
        self.context = context
        from ..utils import get_user_root
        user_root = get_user_root(context.user_id)
        
        # Paths
        internal_skills = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        local_skills = os.path.join(os.getcwd(), "skills")
        user_skills = user_root / "skills"
        user_skills.mkdir(parents=True, exist_ok=True)

        self.manager = SkillManager([
            internal_skills,
            local_skills,
            str(user_skills)
        ])
        
        # Phase 1 Sandbox: Thread pool with timeout
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=5, 
            thread_name_prefix=f"user_{context.user_id}_sandbox"
        )

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return self.manager.get_tool_definitions()

    @property
    def skills(self) -> Dict[str, Callable]:
        # Wrap all skills in a sandboxed execution bridge
        sandboxed_skills = {}
        for name, func in self.manager.skills.items():
            sandboxed_skills[name] = self._make_sandboxed(func)
        return sandboxed_skills

    def _make_sandboxed(self, func: Callable) -> Callable:
        async def sandboxed_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            try:
                # Execute with timeout (e.g., 30s)
                if asyncio.iscoroutinefunction(func):
                    # For async functions, we still use the pool if we want hard thread isolation, 
                    # but usually, we just wrap them in a timeout. 
                    # However, to maintain the "sandbox" feel, we ensure it respects limits.
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=30)
                else:
                    return await asyncio.wait_for(
                        loop.run_in_executor(self._executor, lambda: func(*args, **kwargs)),
                        timeout=30
                    )
            except asyncio.TimeoutError:
                logger.error(f"Skill execution TIMED OUT for user {self.context.user_id}")
                return "Error: Skill execution timed out after 30 seconds."
            except Exception as e:
                logger.error(f"Skill execution ERROR for user {self.context.user_id}: {e}")
                return f"Error: {str(e)}"
        
        return sandboxed_wrapper

    def reload(self):
        self.manager.load_skills()
