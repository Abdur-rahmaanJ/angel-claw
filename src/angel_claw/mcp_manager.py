import json
import asyncio
import logging
import shutil
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fastmcp import Client as FastMCPClient
from fastmcp.client.transports import StreamableHttpTransport
from .config import settings

logger = logging.getLogger("angel-claw-mcp")

class MCPManager:
    def __init__(self):
        self.sessions: Dict[str, Any] = {} # Can be ClientSession or FastMCPClient
        self.exit_stack = AsyncExitStack()
        self.tools_cache: List[Dict[str, Any]] = []
        self.tool_to_server: Dict[str, str] = {}
        self.server_configs = {}
        self.auth_configs = {}
        self.is_connected = False
        self.restarts: Dict[str, int] = {}
        self.max_restarts = 3
        
        # Per-server concurrency limits
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        
        # Robust JSON parsing for .env strings
        self.server_configs = self._parse_json_setting(settings.mcp_servers)
        self.auth_configs = self._parse_json_setting(settings.mcp_auth)

    def _parse_json_setting(self, value: Optional[str]) -> Dict:
        if not value:
            return {}
        try:
            val = value.strip()
            # Remove literal single quotes if present (common in .env)
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            return json.loads(val)
        except Exception as e:
            logger.error(f"Failed to parse MCP JSON setting: {e}")
            return {}

    async def connect(self):
        """Connects to all configured MCP servers independently."""
        if self.is_connected:
            return
            
        for server_name, config in self.server_configs.items():
            if config.get("disabled", False):
                logger.info(f"MCP server '{server_name}' is disabled. Skipping.")
                continue
            
            # Initialize semaphore for concurrency control (ADR 6)
            concurrency = config.get("max_concurrency", settings.mcp_max_concurrency)
            self.semaphores[server_name] = asyncio.Semaphore(concurrency)
            
            await self._connect_server(server_name, config)

        await self._refresh_tools_cache()
        self.is_connected = True

    async def _connect_server(self, server_name: str, config: Dict[str, Any]):
        try:
            auth = self.auth_configs.get(server_name, {})
            
            if "url" in config:
                # Remote SSE Server (e.g. Zapier)
                url = config["url"]
                headers = {}
                if "token" in auth:
                    headers["Authorization"] = f"Bearer {auth['token']}"
                if "headers" in auth:
                    headers.update(auth["headers"])
                
                logger.info(f"Connecting to SSE MCP server '{server_name}' at {url}...")
                try:
                    # Use FastMCP Client as it handles Zapier SSE more robustly
                    transport = StreamableHttpTransport(url, headers=headers)
                    client = FastMCPClient(transport=transport)
                    # Enter the context manager and store the client
                    await self.exit_stack.enter_async_context(client)
                    self.sessions[server_name] = client
                    logger.info(f"Successfully connected to SSE MCP server: {server_name}")
                except Exception as e:
                    self._log_complex_error(server_name, e)
                    await self._handle_server_failure(server_name, config)
            else:
                # Local Stdio Server
                command = config.get("command")
                if not command or not shutil.which(command):
                    logger.warning(f"Skipping Stdio MCP server '{server_name}': command '{command}' not found.")
                    return

                params = StdioServerParameters(
                    command=command, 
                    args=config.get("args", []), 
                    env=config.get("env")
                )
                
                try:
                    read, write = await self.exit_stack.enter_async_context(stdio_client(params))
                    session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    self.sessions[server_name] = session
                    logger.info(f"Successfully connected to Stdio MCP server: {server_name}")
                except Exception as e:
                    self._log_complex_error(server_name, e)
                    await self._handle_server_failure(server_name, config)
        except Exception as e:
            logger.error(f"Unexpected error configuring MCP server '{server_name}': {e}")

    async def _handle_server_failure(self, server_name: str, config: Dict[str, Any]):
        """Restart policy (Plan Section 7)"""
        self.restarts[server_name] = self.restarts.get(server_name, 0) + 1
        if self.restarts[server_name] <= self.max_restarts:
            logger.info(f"Attempting to restart MCP server '{server_name}' (attempt {self.restarts[server_name]})...")
            await asyncio.sleep(2 ** self.restarts[server_name]) # Exponential backoff
            await self._connect_server(server_name, config)
        else:
            logger.error(f"MCP server '{server_name}' failed after {self.max_restarts} attempts.")

    def _log_complex_error(self, server_name: str, e: Exception):
        if hasattr(e, "exceptions"):
            for sub in e.exceptions:
                logger.error(f"Sub-exception connecting to {server_name}: {sub}")
        else:
            logger.error(f"Error connecting to {server_name}: {e}")

    async def _refresh_tools_cache(self):
        self.tools_cache = []
        self.tool_to_server = {}
        for server_name, session in self.sessions.items():
            try:
                # FastMCP and ClientSession have slightly different list_tools signatures
                if isinstance(session, FastMCPClient):
                    tools = await session.list_tools()
                else:
                    resp = await session.list_tools()
                    tools = resp.tools

                for tool in tools:
                    # Normalize tool definition for LiteLLM
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "No description provided.",
                            "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        }
                    }
                    self.tools_cache.append(tool_def)
                    self.tool_to_server[tool.name] = server_name
                logger.info(f"Loaded {len(tools)} tools from MCP server '{server_name}'")
            except Exception as e:
                logger.error(f"Error listing tools for MCP server {server_name}: {e}")

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        if not self.is_connected:
            await self.connect()
        return self.tools_cache

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        server_name = self.tool_to_server.get(tool_name)
        if not server_name or server_name not in self.sessions:
            return f"Error: MCP Server for tool '{tool_name}' not found."
            
        session = self.sessions[server_name]
        semaphore = self.semaphores.get(server_name, asyncio.Semaphore(settings.mcp_max_concurrency))
        
        try:
            async with semaphore:
                # Enforce output size limit (ADR 8.2.2) - Reduced for rate limits
                max_size = settings.mcp_max_output_size
                timeout = self.server_configs.get(server_name, {}).get("timeout", settings.mcp_timeout)
                
                if isinstance(session, FastMCPClient):
                    result = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=timeout)
                    output = [item.text for item in result.content if hasattr(item, 'text')]
                else:
                    result = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=timeout)
                    output = [item.text for item in result.content if hasattr(item, 'text')]
                    
                combined_output = "\n".join(output) if output else "Tool execution returned no text content."
                
                # Security: Output size guard (ADR 8.2.2)
                if len(combined_output) > max_size:
                    logger.warning(f"Tool {tool_name} output ({len(combined_output)} chars) exceeds limit. Truncating.")
                    truncated = combined_output[:max_size]
                    return f"{truncated}\n\n[WARNING: Tool output was truncated to {max_size} chars due to context limits. Please ask for more specific details if needed.]"
                    
                return combined_output
        except asyncio.TimeoutError:
            logger.error(f"Tool {tool_name} timed out after {timeout}s.")
            return f"Error: Tool '{tool_name}' timed out after {timeout}s."
        except Exception as e:
            logger.error(f"Error calling MCP tool '{tool_name}' on server '{server_name}': {e}")
            return f"Error executing MCP tool '{tool_name}': {e}"

    async def disconnect(self):
        await self.exit_stack.aclose()
        self.sessions = {}
        self.is_connected = False

    def get_diagnostics(self) -> Dict[str, Dict[str, Any]]:
        """Returns diagnostic information for all configured servers."""
        diag = {}
        for name, config in self.server_configs.items():
            status = "Disconnected"
            error = None
            if name in self.sessions:
                status = "Connected"
            elif self.restarts.get(name, 0) > self.max_restarts:
                status = "Failed"
                error = f"Max restarts reached ({self.max_restarts})."
            
            diag[name] = {
                "status": status,
                "config": config,
                "restarts": self.restarts.get(name, 0),
                "error": error
            }
        return diag

mcp_manager = MCPManager()
