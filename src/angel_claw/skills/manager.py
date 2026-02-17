import os
import importlib.util
import inspect
from typing import List, Dict, Any, Callable
from litellm import completion

class SkillManager:
    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.skills: Dict[str, Callable] = {}
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
        self.load_skills()

    def load_skills(self):
        self.skills = {}
        for filename in os.listdir(self.skills_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                skill_path = os.path.join(self.skills_dir, filename)
                skill_name = filename[:-3]
                self._load_skill_from_path(skill_name, skill_path)

    def _load_skill_from_path(self, skill_name: str, skill_path: str):
        try:
            spec = importlib.util.spec_from_file_location(skill_name, skill_path)
            module = importlib.util.module_from_spec(spec)
            # Inject 'skill' decorator into the module
            module.skill = skill
            spec.loader.exec_module(module)
            
            # Find functions decorated with @skill
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and getattr(obj, "_is_skill", False):
                    self.skills[name] = obj
        except Exception as e:
            print(f"Error loading skill {skill_name}: {e}")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        tool_defs = []
        for name, func in self.skills.items():
            # Basic docstring parsing for description
            doc = inspect.getdoc(func) or "No description provided."
            # Use inspect to get parameters
            sig = inspect.signature(func)
            params = {
                "type": "object",
                "properties": {},
                "required": []
            }
            for p_name, p in sig.parameters.items():
                p_type = "string" # Default
                if p.annotation == int: p_type = "integer"
                elif p.annotation == bool: p_type = "boolean"
                elif p.annotation == float: p_type = "number"
                
                params["properties"][p_name] = {
                    "type": p_type,
                    "description": f"Parameter {p_name}"
                }
                if p.default == inspect.Parameter.empty:
                    params["required"].append(p_name)
            
            tool_defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": doc,
                    "parameters": params
                }
            })
        return tool_defs

def skill(func):
    func._is_skill = True
    return func
