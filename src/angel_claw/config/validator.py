import litellm
import asyncio
import httpx
from typing import Optional, Tuple

async def validate_llm(model: str, api_key: str, api_base: Optional[str] = None) -> Tuple[bool, str]:
    """
    Performs a minimal test completion to validate the LLM configuration.
    Returns (success, message).
    """
    try:
        # litellm uses environment variables or passed parameters
        # We'll pass them directly to completion
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            api_key=api_key,
            api_base=api_base,
            max_tokens=5
        )
        if response:
            return True, "Connection successful."
    except Exception as e:
        return False, str(e)
    return False, "Unknown error during LLM validation."

async def validate_telegram(token: str) -> Tuple[bool, str]:
    """
    Fetches bot info to validate the Telegram token.
    """
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    bot_name = data["result"].get("username", "Unknown Bot")
                    return True, f"Success: Connected as @{bot_name}"
            return False, f"Failed: {resp.text}"
    except Exception as e:
        return False, str(e)

async def validate_mcp_server(name: str, config: dict) -> Tuple[bool, str]:
    """
    Attempts to connect to an MCP server and list tools to validate it.
    """
    from ..mcp_manager import MCPManager
    manager = MCPManager()
    # Temporarily override servers to just this one
    manager.server_configs = {name: config}
    try:
        # connect() will try to connect to all configured servers
        await manager.connect()
        if name in manager.sessions:
            tools = await manager.get_tool_definitions()
            await manager.disconnect()
            return True, f"Success: Connected and found {len(tools)} tools."
        await manager.disconnect()
        return False, f"Failed to connect to MCP server {name}."
    except Exception as e:
        return False, str(e)

def is_config_complete() -> bool:
    """
    Checks if the essential configuration is present in environment variables.
    """
    from ..config import settings
    # We require at least a MODEL_KEY
    if not settings.api_key or settings.api_key == "your_api_key_here":
        return False
    return True
