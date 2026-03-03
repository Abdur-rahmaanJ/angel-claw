import asyncio
import uuid
import sys
import logging
import warnings
import os
import shutil
import subprocess
import importlib.resources
import questionary
from .config import settings
from .gateway import start as start_gateway
from .cron import cron_manager
from .telegram_bridge import telegram_bridge
from .whatsapp_bridge import whatsapp_bridge
from .mcp_manager import mcp_manager
from .lane_queue.queue import lane_queue
from .lane_queue.process import process_chat_request
from .models import AgentRequest
from .config.validator import is_config_complete
from .config.wizard import run_wizard


# Custom formatter for clean CLI progress output
class CLIProgressFormatter(logging.Formatter):
    def format(self, record):
        if record.msg.startswith("⚙️") or record.msg.startswith("❌"):
            # Return just the message for our progress indicators
            return f"\r{record.msg}\n"
        return super().format(record)


# Suppress all library logging for CLI mode to keep it clean
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("angel-claw-cron").setLevel(logging.ERROR)
logging.getLogger("angel-claw-telegram").setLevel(logging.ERROR)
logging.getLogger("angel-claw-whatsapp").setLevel(logging.ERROR)

# Setup Agent logging for visibility in CLI
agent_logger = logging.getLogger("angel-claw-agent")
agent_logger.setLevel(logging.INFO)
agent_handler = logging.StreamHandler(sys.stdout)
agent_handler.setFormatter(CLIProgressFormatter())
agent_logger.addHandler(agent_handler)
agent_logger.propagate = False  # Don't send to root logger

logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("whatsmeow").setLevel(logging.CRITICAL)
logging.getLogger("Whatsmeow").setLevel(logging.CRITICAL)
logging.getLogger("neonize").setLevel(logging.CRITICAL)

# Suppress litellm specific RuntimeWarning about async_success_handler
warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message="coroutine 'Logging.async_success_handler' was never awaited",
)


def ensure_env():
    """Ensures a .env file exists and is complete in the current working directory."""
    if "--skip-setup" in sys.argv:
        return

    if not os.path.exists(".env") or not is_config_complete():
        print("Angel Claw is not configured yet.")
        if questionary.confirm("Do you want to run the setup wizard?").ask():
            run_wizard()
            # Re-load settings after wizard finishes
            from .config import settings

            settings.__init__(_env_file=".env")
        else:
            if not os.path.exists(".env"):
                print("No .env file found. Creating one from .env.example...")
                try:
                    example_path = importlib.resources.files("angel_claw").joinpath(
                        ".env.example"
                    )
                    if example_path.is_file():
                        shutil.copy(str(example_path), ".env")
                        print(
                            "Created .env file. Please edit it to include your API keys."
                        )
                    else:
                        print("Warning: .env.example not found in package.")
                except Exception as e:
                    print(f"Warning: Could not create .env file: {e}")


async def interactive_chat(model: str = None, api_base: str = None):
    # Register CLI proactive handler
    def cli_proactive_handler(message: str, user_id: str, session_id: str):
        if session_id == "cli-default":
            # Use \r to clear 'You: ' and then print the reminder
            print(f"\r\n[REMINDER] {message}\nYou: ", end="", flush=True)

    cron_manager.register_proactive_handler(cli_proactive_handler)

    # Start background workers silently
    lane_queue.start_workers()
    cron_task = asyncio.create_task(cron_manager.run())
    telegram_task = asyncio.create_task(telegram_bridge.run())
    whatsapp_task = asyncio.create_task(whatsapp_bridge.run())

    # Use a persistent session ID for CLI by default
    session_id = "cli-default"

    print(f"\n--- Angel Claw CLI Chat ---")
    print(f"Model: {model or settings.model}")
    if api_base or settings.api_base:
        print(f"API Base: {api_base or settings.api_base}")
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

            print("Thinking...", end="\r", flush=True)
            request = AgentRequest(
                session_id=session_id,
                message=user_input,
                user_id="cli",
                model=model,
                api_base=api_base,
            )
            response = await process_chat_request(request)
            # Clear the "thinking" line if it was still there
            print(" " * 40, end="\r", flush=True)
            print(f"Assistant: {response}\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

    # Cancel and cleanup all background tasks
    for task in [cron_task, telegram_task, whatsapp_task]:
        task.cancel()

    # Wait for tasks to finish cancelling
    await asyncio.gather(
        *[cron_task, telegram_task, whatsapp_task], return_exceptions=True
    )

    # Cleanup bridge resources
    await whatsapp_bridge.close()
    await telegram_bridge.close()
    await mcp_manager.disconnect()


def run_shopyo_command(cmd_list):
    """Runs a shopyo command via manage.py in the app directory."""
    app_dir = importlib.resources.files("angel_claw").joinpath("app")
    manage_py = os.path.join(str(app_dir), "manage.py")
    
    # We must be in the app directory for shopyo to find modules
    env = os.environ.copy()
    # Ensure the package root is in PYTHONPATH so engine/models can be imported
    package_root = os.path.abspath(os.path.join(str(app_dir), "..", ".."))
    env["PYTHONPATH"] = f"{package_root}:{env.get('PYTHONPATH', '')}"
    
    subprocess.run([sys.executable, manage_py] + cmd_list, cwd=str(app_dir), env=env)


def start_web_server():
    """Initializes and starts the Shopyo web application."""
    ensure_env()
    app_dir = importlib.resources.files("angel_claw").joinpath("app")
    db_path = os.path.join(str(app_dir), "shopyo.db")
    
    if not os.path.exists(db_path):
        print("Initializing database...")
        run_shopyo_command(["initialise"])
    
    # Always run seed to ensure admin user and roles exist with latest config
    print("Seeding database with default users and roles...")
    run_shopyo_command(["shopyo-seed"])
    
    print("Starting Angel Claw Web Server...")
    run_shopyo_command(["run"])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        if "--reconfigure" in sys.argv:
            run_wizard()

        ensure_env()
        model_override = None
        api_base_override = None
        # Parse arguments for model and api_base
        for i, arg in enumerate(sys.argv):
            if arg == "--model" and i + 1 < len(sys.argv):
                model_override = sys.argv[i + 1]
            if arg == "--api-base" and i + 1 < len(sys.argv):
                api_base_override = sys.argv[i + 1]

        asyncio.run(interactive_chat(model=model_override, api_base=api_base_override))
    elif len(sys.argv) > 1 and sys.argv[1] == "serve":
        start_web_server()
    elif len(sys.argv) > 1 and sys.argv[1] == "tutorial":
        ensure_env()
        # Tutorial implementation will go here
        from .tutorial import run_tutorial

        asyncio.run(run_tutorial())
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

            async def test_diagnostics():
                from .config.validator import validate_llm

                print("\n--- Angel Claw Diagnostics ---")

                # 1. LLM Test
                print(f"Testing LLM ({settings.model})...")
                l_success, l_msg = await validate_llm(
                    settings.model, settings.api_key, settings.api_base
                )
                if l_success:
                    print(f"✅ LLM: {l_msg}")
                else:
                    print(f"❌ LLM: {l_msg}")
                    print(
                        "👉 Suggestion: Run 'angel-claw chat --reconfigure' to check your API key."
                    )

                # 2. MCP Test
                print("\nTesting MCP connections...")
                await mcp_manager.connect()
                diagnostics = mcp_manager.get_diagnostics()
                for name, info in diagnostics.items():
                    if info["status"] == "Connected":
                        print(f"✅ MCP [{name}]: Connected")
                    else:
                        print(f"❌ MCP [{name}]: {info['status']}")
                        if info["error"]:
                            print(f"   Error: {info['error']}")
                await mcp_manager.disconnect()

            asyncio.run(test_diagnostics())
        else:
            print("Usage: angel-claw mcp [list|test]")
    else:
        # Default to starting the gateway if no subcommand or 'serve'
        start_gateway()


if __name__ == "__main__":
    main()
