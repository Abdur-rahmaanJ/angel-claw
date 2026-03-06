import os
import logging
import asyncio
import concurrent.futures
import inspect
import json
from typing import List, Dict, Any, Callable, Optional
from ..skills.manager import SkillManager
from ..models import UserContext
from ..mcp_manager import mcp_manager

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

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        local_tools = self.manager.get_tool_definitions()
        mcp_tools = await mcp_manager.get_tool_definitions()
        return local_tools + mcp_tools

    @property
    def skills(self) -> Dict[str, Callable]:
        # DEPRECATED: Use call_tool instead for better sandboxing
        # Wrap all skills in a sandboxed execution bridge
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

            sandboxed_func = self._make_sandboxed(func)
            result = await sandboxed_func(**arguments)
            return self._sanitize_output(str(result))
            
        elif name in mcp_manager.tool_to_server:
            # Sandbox MCP calls as well
            try:
                result = await asyncio.wait_for(
                    mcp_manager.call_tool(name, arguments),
                    timeout=45 # MCP might need more time
                )
                return self._sanitize_output(str(result))
            except asyncio.TimeoutError:
                return f"Error: MCP tool '{name}' timed out."
            except Exception as e:
                return f"Error executing MCP tool '{name}': {e}"
        else:
            return f"Error: Tool '{name}' not found."

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
