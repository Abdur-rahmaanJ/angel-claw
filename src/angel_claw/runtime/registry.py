import os
import logging
import asyncio
import concurrent.futures
import inspect
import json
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from ..skills.manager import SkillManager
from ..skills.defaults import (
    EAGER_MODULES,
    MODULE_DESCRIPTIONS,
    module_enabled,
    tool_enabled,
)
from ..models import UserContext
from ..mcp_manager import mcp_manager
from ..config import settings

logger = logging.getLogger("angel-claw-registry")


class TieredSkillRegistry:
    """Manages global and user-specific skills with execution sandboxing (Threads or Docker)."""

    def __init__(self, context: UserContext):
        self.context = context
        from ..utils import get_user_root

        self.user_root = get_user_root(context.user_id)

        internal_skills = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "skills"
        )
        local_skills = os.path.join(os.getcwd(), "skills")
        user_skills = self.user_root / "skills"
        user_skills.mkdir(parents=True, exist_ok=True)

        self.manager = SkillManager([internal_skills, local_skills, str(user_skills)])
        self._config_cache: tuple[float, dict] | None = None
        # Modules whose tool schemas were requested with load_skill_tools.
        self._loaded_modules: set[str] = set()

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=5, thread_name_prefix=f"user_{context.user_id}_sandbox"
        )

    def get_skill_config(self) -> dict:
        """The user's skill config, cached until the file changes."""
        path = self.user_root / "skill_config.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return {}
        if self._config_cache and self._config_cache[0] == mtime:
            return self._config_cache[1]
        try:
            with open(path) as f:
                config = json.load(f)
            config = config if isinstance(config, dict) else {}
        except Exception as e:
            logger.error(f"Error reading skill config: {e}")
            config = {}
        self._config_cache = (mtime, config)
        return config

    def _tool_enabled(self, name: str) -> bool:
        module = self.manager.skill_modules.get(name, name)
        if not tool_enabled(self.get_skill_config(), module, name):
            return False
        return module in EAGER_MODULES or module in self._loaded_modules

    def is_module_enabled(self, module: str) -> bool:
        return module_enabled(self.get_skill_config(), module)

    def is_module_loaded(self, module: str) -> bool:
        return module in EAGER_MODULES or module in self._loaded_modules

    def load_module(self, module: str) -> str:
        """Expose a lazily-loaded module's tools for later turns."""
        module = (module or "").strip().lower()
        modules = self.manager.get_modules()
        if module not in modules:
            known = ", ".join(sorted(modules))
            return f"Error: unknown skill module '{module}'. Available: {known}."
        if not self.is_module_enabled(module):
            return (
                f"Error: '{module}' is disabled in Settings -> Skills. "
                "Enable it there first."
            )
        if self.is_module_loaded(module):
            return f"'{module}' tools are already loaded."
        self._loaded_modules.add(module)
        tools = ", ".join(sorted(modules[module]["functions"]))
        return (
            f"Loaded '{module}'. New tools available now: {tools}. "
            "Call them directly."
        )

    def describe_modules(self) -> str:
        """Human/model readable inventory for list_skill_modules."""
        modules = self.manager.get_modules()
        lines = []
        for module, info in sorted(modules.items()):
            if not self.is_module_enabled(module):
                status = "disabled in Settings"
            elif self.is_module_loaded(module):
                status = "loaded"
            else:
                status = "not loaded"
            description = MODULE_DESCRIPTIONS.get(module) or info.get("description") or ""
            lines.append(
                f"- {module}: {status} ({len(info['functions'])} tools) - {description}"
            )
        return "Skill modules:\n" + "\n".join(lines)

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        local_tools = [
            tool
            for tool in self.manager.get_tool_definitions()
            if self._tool_enabled(tool["function"]["name"])
        ]
        mcp_tools = await mcp_manager.get_tool_definitions()
        return local_tools + mcp_tools

    @property
    def skills(self) -> Dict[str, Callable]:
        sandboxed_skills = {}
        for name, func in self.manager.skills.items():
            if self._tool_enabled(name):
                sandboxed_skills[name] = self._make_sandboxed(func)
        return sandboxed_skills

    async def call_tool(
        self, name: str, arguments: Dict[str, Any], session_id: str
    ) -> str:
        """Unified, sandboxed tool caller for local and MCP tools."""
        if not isinstance(arguments, dict):
            arguments = {}

        if name in self.manager.skills:
            if not self._tool_enabled(name):
                return f"Error: Tool '{name}' is disabled in Skills settings."
            func = self.manager.skills[name]

            sig = inspect.signature(func)

            if "session_id" in sig.parameters:
                if "session_id" not in arguments:
                    arguments["session_id"] = session_id

            if "user_id" in sig.parameters:
                if "user_id" not in arguments:
                    arguments["user_id"] = self.context.user_id

            if "email" in sig.parameters:
                if "email" not in arguments:
                    arguments["email"] = self.context.email

            if "roles" in sig.parameters:
                if "roles" not in arguments:
                    arguments["roles"] = self.context.roles

            if "is_admin" in sig.parameters:
                if "is_admin" not in arguments:
                    arguments["is_admin"] = self.context.is_admin

            if settings.docker_sandboxing_enabled:
                result = await self._call_in_docker(name, arguments)
            else:
                sandboxed_func = self._make_sandboxed(func)
                result = await sandboxed_func(**arguments)

            return self._sanitize_output(str(result))

        elif name in mcp_manager.tool_to_server:
            try:
                result = await asyncio.wait_for(
                    mcp_manager.call_tool(name, arguments), timeout=45
                )
                return self._sanitize_output(str(result))
            except asyncio.TimeoutError:
                return f"Error: MCP tool '{name}' timed out."
            except Exception as e:
                return f"Error executing MCP tool '{name}': {e}"
        else:
            return f"Error: Tool '{name}' not found."

    async def _call_in_docker(self, name: str, arguments: Dict[str, Any]) -> str:
        skill_file = None
        for d in self.manager.skills_dirs:
            if not os.path.exists(d):
                continue
            for f in os.listdir(d):
                if f.endswith(".py"):
                    with open(os.path.join(d, f), "r") as file_content:
                        if f"def {name}" in file_content.read():
                            skill_file = os.path.abspath(os.path.join(d, f))
                            break
            if skill_file:
                break

        if not skill_file:
            return f"Error: Could not locate source file for skill '{name}'"

        runner_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "container_runner.py")
        )

        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
            "--runtime",
            settings.docker_runtime,
            "-v",
            f"{skill_file}:/app/skill.py:ro",
            "-v",
            f"{runner_path}:/app/runner.py:ro",
            settings.docker_image,
            "python",
            "/app/runner.py",
            "/app/skill.py",
            name,
            json.dumps(arguments),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=settings.docker_timeout
            )

            if process.returncode != 0:
                logger.error(f"Docker execution failed: {stderr.decode()}")
                return f"Error: Sandbox execution failed: {stderr.decode()}"

            output = stdout.decode().strip()
            try:
                data = json.loads(output)
                if data["status"] == "success":
                    return data["result"]
                else:
                    return f"Error: {data['message']}"
            except json.JSONDecodeError:
                return f"Error: Invalid output from sandbox: {output}"

        except asyncio.TimeoutError:
            return "Error: Skill execution timed out in Docker sandbox."
        except Exception as e:
            logger.error(f"Docker sandbox error: {e}")
            return f"Error: Sandbox infrastructure failure: {e}"

    def _sanitize_output(self, output: str) -> str:
        max_len = 15000
        if len(output) > max_len:
            output = output[:max_len] + "... [TRUNCATED]"

        forbidden_prefixes = ["SYSTEM:", "ASSISTANT:", "USER:", "IMPORTANT:"]
        for prefix in forbidden_prefixes:
            if output.upper().startswith(prefix):
                output = "[SANITIZED] " + output
                break

        return output

    def _make_sandboxed(self, func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        async def sandboxed_wrapper(*args, **kwargs):
            try:
                if is_async:
                    result = await asyncio.wait_for(func(**kwargs), timeout=30)
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(self._executor, lambda: func(**kwargs)),
                        timeout=30,
                    )
                return result
            except asyncio.TimeoutError:
                return f"Error: Skill timed out after 30 seconds."
            except Exception as e:
                return f"Error: {str(e)}"

        return sandboxed_wrapper

    def reload(self):
        self.manager.load_skills()
