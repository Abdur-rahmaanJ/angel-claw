import os
import logging
import asyncio
import concurrent.futures
import inspect
import json
import subprocess
from typing import List, Dict, Any, Callable, Optional
from ..skills.manager import SkillManager
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
        
        # Paths
        internal_skills = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        local_skills = os.path.join(os.getcwd(), "skills")
        user_skills = self.user_root / "skills"
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

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        local_tools = self.manager.get_tool_definitions()
        mcp_tools = await mcp_manager.get_tool_definitions()
        return local_tools + mcp_tools

    @property
    def skills(self) -> Dict[str, Callable]:
        # DEPRECATED: Use call_tool instead for better sandboxing
        sandboxed_skills = {}
        for name, func in self.manager.skills.items():
            sandboxed_skills[name] = self._make_sandboxed(func)
        return sandboxed_skills

    async def call_tool(self, name: str, arguments: Dict[str, Any], session_id: str) -> str:
        """Unified, sandboxed tool caller for local and MCP tools."""
        if name in self.manager.skills:
            func = self.manager.skills[name]
            
            # Inject context
            sig = inspect.signature(func)
            if "session_id" in sig.parameters:
                if "session_id" not in arguments:
                    arguments["session_id"] = session_id

            if "user_id" in sig.parameters:
                if "user_id" not in arguments:
                    arguments["user_id"] = self.context.user_id

            # Phase 2: Docker Sandboxing (if enabled)
            if settings.docker_sandboxing_enabled:
                result = await self._call_in_docker(name, arguments)
            else:
                # Phase 1: Thread Sandbox
                sandboxed_func = self._make_sandboxed(func)
                result = await sandboxed_func(**arguments)
                
            return self._sanitize_output(str(result))
            
        elif name in mcp_manager.tool_to_server:
            # Sandbox MCP calls
            try:
                result = await asyncio.wait_for(
                    mcp_manager.call_tool(name, arguments),
                    timeout=45 
                )
                return self._sanitize_output(str(result))
            except asyncio.TimeoutError:
                return f"Error: MCP tool '{name}' timed out."
            except Exception as e:
                return f"Error executing MCP tool '{name}': {e}"
        else:
            return f"Error: Tool '{name}' not found."

    async def _call_in_docker(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes a skill inside a transient Docker container (optionally with gVisor)."""
        # Find which file contains this skill
        skill_file = None
        for d in self.manager.skills_dirs:
            if not os.path.exists(d): continue
            for f in os.listdir(d):
                if f.endswith(".py"):
                    # This is a bit slow but necessary if we don't track file-to-func mapping
                    with open(os.path.join(d, f), 'r') as file_content:
                        if f"def {name}" in file_content.read():
                            skill_file = os.path.abspath(os.path.join(d, f))
                            break
            if skill_file: break

        if not skill_file:
            return f"Error: Could not locate source file for skill '{name}'"

        runner_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "container_runner.py"))
        
        # Docker Command Construction
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "128m",
            "--cpus", "0.5",
            "--runtime", settings.docker_runtime,
            "-v", f"{skill_file}:/app/skill.py:ro",
            "-v", f"{runner_path}:/app/runner.py:ro",
            settings.docker_image,
            "python", "/app/runner.py", "/app/skill.py", name, json.dumps(arguments)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=settings.docker_timeout)
            
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
        """Sanitizes tool output to prevent prompt injection from external sources."""
        # Simple defense: ensure tool output doesn't look like system instructions
        # and limit total length to prevent context explosion/DOS
        max_len = 15000
        if len(output) > max_len:
            output = output[:max_len] + "... [TRUNCATED]"
            
        # Strip potential instruction-like prefixes that might trick the LLM
        forbidden_prefixes = ["SYSTEM:", "ASSISTANT:", "USER:", "IMPORTANT:"]
        for prefix in forbidden_prefixes:
            if output.upper().startswith(prefix):
                output = "[SANITIZED] " + output
                break
                
        return output

    def _make_sandboxed(self, func: Callable) -> Callable:
        async def sandboxed_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            try:
                # Execute with timeout (e.g., 30s)
                if asyncio.iscoroutinefunction(func):
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
