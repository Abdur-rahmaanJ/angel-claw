import asyncio
import uuid
import sys
import logging
import warnings
import os
import shutil
import importlib.resources
from .agent import Agent
from .config import settings
from .gateway import start as start_gateway
from .cron import cron_manager
from .telegram_bridge import telegram_bridge
from .whatsapp_bridge import whatsapp_bridge
from .mcp_manager import mcp_manager

# Suppress all library logging for CLI mode to keep it clean
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("angel-claw-cron").setLevel(logging.ERROR)
logging.getLogger("angel-claw-telegram").setLevel(logging.ERROR)
logging.getLogger("angel-claw-whatsapp").setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("whatsmeow").setLevel(logging.CRITICAL)
logging.getLogger("Whatsmeow").setLevel(logging.CRITICAL)
logging.getLogger("neonize").setLevel(logging.CRITICAL)

# Suppress litellm specific RuntimeWarning about async_success_handler
warnings.filterwarnings("ignore", category=RuntimeWarning, message="coroutine 'Logging.async_success_handler' was never awaited")

def ensure_env():
    """Ensures a .env file exists in the current working directory."""
    if not os.path.exists(".env"):
        print("No .env file found. Creating one from .env.example...")
        try:
            # Try to get .env.example from the package resources
            # In modern python (3.11+), importlib.resources.files is preferred
            example_path = importlib.resources.files("angel_claw").joinpath(".env.example")
            if example_path.is_file():
                shutil.copy(str(example_path), ".env")
                print("Created .env file. Please edit it to include your API keys.")
            else:
                print("Warning: .env.example not found in package.")
        except Exception as e:
            print(f"Warning: Could not create .env file: {e}")

async def interactive_chat(model: str = None):
    # Register CLI proactive handler
    def cli_proactive_handler(message: str, user_id: str, session_id: str):
        if session_id == "cli-default":
            # Use \r to clear 'You: ' and then print the reminder
            print(f"\r\n[REMINDER] {message}\nYou: ", end="", flush=True)

    cron_manager.register_proactive_handler(cli_proactive_handler)

    # Start background workers silently
    cron_task = asyncio.create_task(cron_manager.run())
    telegram_task = asyncio.create_task(telegram_bridge.run())
    whatsapp_task = asyncio.create_task(whatsapp_bridge.run())
    
    # Use a persistent session ID for CLI by default
    session_id = "cli-default"
    agent = Agent(session_id, model=model)
    
    print(f"\n--- Angel Claw CLI Chat ---")
    print(f"Model: {agent.model}")
    print(f"Session: {session_id}")
    print("Type 'exit' or 'quit' to stop.\n")
    
    # Give background tasks a moment to initialize before showing 'You:'
    await asyncio.sleep(0.5) 
    
    while True:
        try:
            # Use to_thread to keep the event loop running for background tasks while waiting for input
            user_input = await asyncio.to_thread(input, "You: ")
            user_input = user_input.strip()
            if user_input.lower() in ["exit", "quit"]:
                break
            if not user_input:
                continue
                
            print("\nAssistant: ", end="", flush=True)
            # Use asyncio for chat as it is async
            response = await agent.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")
    
    # Cancel and cleanup all background tasks
    for task in [cron_task, telegram_task, whatsapp_task]:
        task.cancel()
    
    # Wait for tasks to finish cancelling
    await asyncio.gather(*[cron_task, telegram_task, whatsapp_task], return_exceptions=True)
    
    # Cleanup bridge resources
    await whatsapp_bridge.close()
    await mcp_manager.disconnect()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        ensure_env()
        model_override = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(interactive_chat(model_override))
    elif len(sys.argv) > 1 and sys.argv[1] == "login-whatsapp":
        ensure_env()
        from .whatsapp_bridge import whatsapp_bridge
        print("--- Angel Claw WhatsApp Login ---")
        print("Ensure WHATSAPP_ENABLED=True is set in your .env")
        # Force enable for this command
        whatsapp_bridge.enabled = True
        asyncio.run(whatsapp_bridge.run())
    elif len(sys.argv) > 1 and sys.argv[1] == "mcp":
        if len(sys.argv) > 2 and sys.argv[2] == "list":
            async def list_mcp():
                await mcp_manager.connect()
                tools = await mcp_manager.get_tool_definitions()
                print(f"\n--- Discovered {len(tools)} MCP Tools ---")
                for t in tools:
                    print(f"- {t['function']['name']}: {t['function']['description']}")
                await mcp_manager.disconnect()
            asyncio.run(list_mcp())
        elif len(sys.argv) > 2 and sys.argv[2] == "test":
            async def test_mcp():
                print("Testing MCP connections...")
                await mcp_manager.connect()
                for name, session in mcp_manager.sessions.items():
                    print(f"✅ Connected to: {name}")
                await mcp_manager.disconnect()
            asyncio.run(test_mcp())
        else:
            print("Usage: angel-claw mcp [list|test]")
    else:
        # Default to starting the gateway if no subcommand or 'serve'
        start_gateway()

if __name__ == "__main__":
    main()
