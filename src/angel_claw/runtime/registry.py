import os
import logging
from typing import List, Dict, Any, Callable, Optional
from ..skills.manager import SkillManager
from ..models import UserContext

logger = logging.getLogger("angel-claw-registry")

class TieredSkillRegistry:
    """Manages global and user-specific skills."""
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

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return self.manager.get_tool_definitions()

    @property
    def skills(self) -> Dict[str, Callable]:
        return self.manager.skills

    def reload(self):
        self.manager.load_skills()
