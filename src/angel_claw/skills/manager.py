import os
import importlib.util
import inspect
import hashlib
import logging
from typing import List, Dict, Any, Callable, Union

logger = logging.getLogger("angel-claw-skills")


class SkillManager:
    def __init__(self, skills_dirs: Union[str, List[str]]):
        if isinstance(skills_dirs, str):
            self.skills_dirs = [skills_dirs]
        else:
            self.skills_dirs = skills_dirs

        self.skills: Dict[str, Callable] = {}
        self._tool_defs_cache: List[Dict[str, Any]] = []
        self._file_checksum: str = ""
        for d in self.skills_dirs:
            if not os.path.exists(d):
                os.makedirs(d)
        self.load_skills()

    def _get_dir_checksum(self) -> str:
        """Get a checksum of all skill files to detect changes."""
        hashes = []
        for d in self.skills_dirs:
            if not os.path.exists(d):
                continue
            for filename in sorted(os.listdir(d)):
                if filename.endswith(".py") and filename != "__init__.py":
                    filepath = os.path.join(d, filename)
                    mtime = os.path.getmtime(filepath)
                    hashes.append(f"{filename}:{mtime}")
        return hashlib.md5("".join(hashes).encode()).hexdigest()

    def _needs_reload(self) -> bool:
        """Check if skills need to be reloaded."""
        current_checksum = self._get_dir_checksum()
        if current_checksum != self._file_checksum:
            self._file_checksum = current_checksum
            return True
        return False

    def load_skills(self):
        """Load skills from all skill directories."""
        self.skills = {}
        for d in self.skills_dirs:
            if not os.path.exists(d):
                continue
            for filename in os.listdir(d):
                if filename.endswith(".py") and filename != "__init__.py":
                    skill_path = os.path.join(d, filename)
                    skill_name = filename[:-3]
                    self._load_skill_from_path(skill_name, skill_path)

        # Update checksum after loading
        self._file_checksum = self._get_dir_checksum()
        # Clear cache since skills changed
        self._tool_defs_cache = []

    def reload_if_needed(self):
        """Smart reload - only reload if files changed."""
        if self._needs_reload():
            self.load_skills()

    def list_skills(self) -> List[str]:
        """Returns a list of all loaded skill names."""
        self.reload_if_needed()
        return list(self.skills.keys())

    def get_skill_details(self) -> Dict[str, str]:
        """Returns a mapping of skill names to their docstrings."""
        self.reload_if_needed()
        details = {}
        for name, func in self.skills.items():
            doc = inspect.getdoc(func) or "No description provided."
            details[name] = doc
        return details

    def _load_skill_from_path(self, skill_name: str, skill_path: str):
        try:
            spec = importlib.util.spec_from_file_location(skill_name, skill_path)
            module = importlib.util.module_from_spec(spec)
            module.skill = skill
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and getattr(obj, "_is_skill", False):
                    self.skills[name] = obj
        except Exception as e:
            logger.debug(f"Error loading skill {skill_name}: {e}")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions with caching."""
        # Use cache if available
        if self._tool_defs_cache:
            return self._tool_defs_cache

        # Check if reload needed before building
        self.reload_if_needed()

        tool_defs = []
        for name, func in self.skills.items():
            doc = inspect.getdoc(func) or "No description provided."
            sig = inspect.signature(func)
            params = {"type": "object", "properties": {}, "required": []}
            for p_name, p in sig.parameters.items():
                if p_name in ["session_id", "user_id"]:
                    continue
                p_type = "string"
                if p.annotation == int:
                    p_type = "integer"
                elif p.annotation == bool:
                    p_type = "boolean"
                elif p.annotation == float:
                    p_type = "number"

                params["properties"][p_name] = {
                    "type": p_type,
                    "description": f"Parameter {p_name}",
                }
                if p.default == inspect.Parameter.empty:
                    params["required"].append(p_name)

            tool_defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": doc,
                        "parameters": params,
                    },
                }
            )

        # Cache the result
        self._tool_defs_cache = tool_defs
        return tool_defs


def skill(func):
    func._is_skill = True
    return func
