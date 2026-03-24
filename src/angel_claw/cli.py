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
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
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


logger = logging.getLogger("angel-claw-cli")


# Custom formatter for clean CLI progress output
class CLIProgressFormatter(logging.Formatter):
    def format(self, record):
        if record.msg.startswith("⚙️") or record.msg.startswith("❌"):
            # Return just the message for our progress indicators
            return f"\r{record.msg}\n"
        return super().format(record)


# Suppress all library logging for CLI mode to keep it clean
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("angel-claw-cron").setLevel(logging.INFO)
logging.getLogger("angel-claw-telegram").setLevel(logging.INFO)
logging.getLogger("angel-claw-whatsapp").setLevel(logging.INFO)
logging.getLogger("telegram.ext.Updater").setLevel(logging.CRITICAL)

# Setup Agent logging for visibility in CLI
agent_logger = logging.getLogger("angel-claw-agent")
agent_logger.setLevel(logging.INFO)
agent_handler = logging.StreamHandler(sys.stdout)
agent_handler.setFormatter(CLIProgressFormatter())
agent_logger.addHandler(agent_handler)

console = Console()
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
warnings.filterwarnings("ignore", category=UserWarning, module="click")
try:
    from sqlalchemy.exc import LegacyAPIWarning, SAWarning

    warnings.filterwarnings("ignore", category=LegacyAPIWarning)
    warnings.filterwarnings("ignore", category=SAWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="sqlalchemy")
except ImportError:
    pass
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Suppress Flask/Werkzeug request logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)


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

    # Audit: Multi-Tenant Isolation - Verify CLI Identity
    from .engine import AngelClawEngine
    from .models import UserContext

    engine = AngelClawEngine()

    # Dev mode for testing without full Shopyo setup
    if os.environ.get("CLI_DEV_MODE", "").lower() == "true":
        context = UserContext(
            user_id="dev-user",
            email="dev@local",
            roles=["admin"],
            channel_type="cli",
            channel_identifier="cli-dev",
        )
    else:
        cli_key = os.environ.get("CLI_API_KEY")
        if not cli_key:
            print("❌ Error: CLI_API_KEY not found in .env")
            print(
                "Please generate an API key in the web dashboard and add it to your .env as CLI_API_KEY."
            )
            print("Or set CLI_DEV_MODE=true for development.")
            return

        context = engine.validate_api_key(cli_key)
        if not context:
            print("❌ Error: Invalid or inactive CLI_API_KEY.")
            return

    # Start background workers silently
    lane_queue.start_workers()
    cron_task = asyncio.create_task(cron_manager.run())
    telegram_task = asyncio.create_task(telegram_bridge.run())
    whatsapp_task = asyncio.create_task(whatsapp_bridge.run())

    # Use a persistent session ID for CLI by default
    session_id = "cli-default"

    print(f"\n--- Angel Claw CLI Chat ---")
    print(f"User: {context.email}")
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
            # Use the verified context for the request
            response = await process_chat_request(
                AgentRequest(
                    session_id=session_id,
                    message=user_input,
                    user_id=context.user_id,
                    model=model,
                    api_base=api_base,
                ),
                context,
            )
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


def run_shopyo_command(cmd_list, quiet=False):
    """Runs a shopyo command via manage.py in the app directory."""
    app_dir = importlib.resources.files("angel_claw").joinpath("app")
    manage_py = os.path.join(str(app_dir), "manage.py")

    # We must be in the app directory for shopyo to find modules
    env = os.environ.copy()
    # Ensure the package root is in PYTHONPATH so engine/models can be imported
    package_root = os.path.abspath(os.path.join(str(app_dir), "..", ".."))
    env["PYTHONPATH"] = f"{package_root}:{env.get('PYTHONPATH', '')}"
    env["SHOPYO_QUIET"] = "True"

    # Force Shopyo to use our standardized user data DB path
    db_abs_path = os.path.abspath(os.path.expanduser(settings.db_path))
    env["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_abs_path}"
    config_name = os.environ.get("FLASK_ENV", "production")
    env["FLASK_APP"] = f"app:create_app('{config_name}')"
    env["FLASK_ENV"] = config_name


    # Suppress output if quiet
    stdout = subprocess.DEVNULL if quiet else None
    stderr = subprocess.DEVNULL if quiet else None

    subprocess.run(
        [sys.executable, manage_py, "--config", config_name] + cmd_list,
        cwd=str(app_dir),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )


def start_web_server(port=5000):
    """Initializes and starts the Shopyo web application."""
    ensure_env()

    app_dir = importlib.resources.files("angel_claw").joinpath("app")

    # Crucial: Add app_dir to sys.path so AngelClawEngine can find 'app' and 'init'
    # when running in the same process (background bridges thread)
    app_path_str = str(app_dir)
    if app_path_str not in sys.path:
        sys.path.insert(0, app_path_str)

    # Check if DB exists in standardized path
    if not os.path.exists(settings.db_path):
        print("⚙️  Initializing database...", end="\r", flush=True)
        # Use --no-clear-migration to preserve our hand-crafted migrations
        run_shopyo_command(["initialise", "--no-clear-migration"], quiet=True)
        print("⚙️  Initializing database... Done.")

    print("⚙️  Syncing users and roles... Done.")

    config_name = os.environ.get("FLASK_ENV", "development")
    from app import create_app

    app = create_app(config_name)

    # Start background bridges in a separate thread
    import threading

    def run_bridges(shared_app):
        # Silence all bridge logging for clean serve mode
        logging.getLogger("angel-claw-cron").setLevel(logging.INFO)
        logging.getLogger("angel-claw-telegram").setLevel(logging.INFO)
        logging.getLogger("angel-claw-whatsapp").setLevel(logging.INFO)

        # Ensure path is correct in this thread too
        app_dir = importlib.resources.files("angel_claw").joinpath("app")
        app_path_str = str(app_dir)
        if app_path_str not in sys.path:
            sys.path.insert(0, app_path_str)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def start_all():
            from .telegram_bridge import telegram_bridge
            from .whatsapp_bridge import whatsapp_bridge
            from .cron import cron_manager

            # Inject shared app into engine for all bridges
            telegram_bridge.engine.set_app(shared_app)
            whatsapp_bridge.engine.set_app(shared_app)

            try:
                # These must be called INSIDE the running loop
                logger.info("Bridge thread: starting workers and bridges")
                lane_queue.start_workers()
                asyncio.create_task(telegram_bridge.run())
                asyncio.create_task(whatsapp_bridge.run())
                asyncio.create_task(cron_manager.run())
                logger.info("Bridge thread: tasks created")
            except Exception as e:
                logger.error(f"Error starting bridges: {e}")
                import traceback

                logger.error(traceback.format_exc())

        loop.run_until_complete(start_all())
        try:
            loop.run_forever()
        except Exception as e:
            logger.error(f"Fatal error in bridge thread: {e}", exc_info=True)

    bridge_thread = threading.Thread(target=run_bridges, args=(app,), daemon=True)
    bridge_thread.start()

    table = Table.grid(padding=(0, 1))
    table.add_column(style="cyan")
    table.add_column(style="white")

    table.add_row("🔗  URL:", f"http://127.0.0.1:{port}")
    table.add_row("👤  User:", "admin@admin.com")
    table.add_row("🔑  Pass:", "admin")
    table.add_row("", "")
    table.add_row("🤖  Bridges:", "[green]active in background[/green]")
    table.add_row("⏹️   Stop:", "[bold red]Ctrl+C[/bold red]")

    dashboard = Panel(
        table,
        title="[bold green]🪽 Angel Claw[/bold green]",
        subtitle="[dim]Powered by Shopyo[/dim]",
        expand=False,
        border_style="bright_blue",
        padding=(1, 4),
    )

    console.print("\n")
    console.print(dashboard)
    console.print("\n")

    # Start the Flask development server directly
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


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
        port = 5000
        for i, arg in enumerate(sys.argv):
            if (arg == "--port" or arg == "-p") and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    print(f"Error: Invalid port number '{sys.argv[i + 1]}'")
                    sys.exit(1)
        start_web_server(port=port)
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
    elif len(sys.argv) > 1 and sys.argv[1] == "confirm-user":
        if len(sys.argv) > 2:
            email = sys.argv[2]
            run_shopyo_command(["shopyo-confirm-user", email])
        else:
            print("Usage: angel-claw confirm-user <email>")
    elif len(sys.argv) > 1 and sys.argv[1] == "promote-user":
        if len(sys.argv) > 2:
            email = sys.argv[2]
            run_shopyo_command(["shopyo-promote-user", email])
        else:
            print("Usage: angel-claw promote-user <email>")
    elif len(sys.argv) > 1 and sys.argv[1] == "create-admin":
        if len(sys.argv) > 3:
            email = sys.argv[2]
            password = sys.argv[3]
            run_shopyo_command(["shopyo-create-admin", email, password])
        else:
            print("Usage: angel-claw create-admin <email> <password>")
    elif len(sys.argv) > 1 and sys.argv[1] == "setup":
        print("🪽  Starting Angel Claw Setup...")
        
        # Parse flags
        email = None
        password = None
        force_yes = "--yes" in sys.argv or "-y" in sys.argv
        
        for i, arg in enumerate(sys.argv):
            if arg == "--email" and i + 1 < len(sys.argv):
                email = sys.argv[i + 1]
            if arg == "--password" and i + 1 < len(sys.argv):
                password = sys.argv[i + 1]

        # 1. Initialize Database
        db_path = os.path.abspath(os.path.expanduser(settings.db_path))
        if os.path.exists(db_path):
            if not force_yes:
                print(f"⚠️  Database already exists at {db_path}")
                if not questionary.confirm("Overwrite and re-initialize?", default=False).ask():
                    print("Aborting setup.")
                    return
            os.remove(db_path)
            
        print("⚙️  Step 1/2: Initializing database tables...")
        # shopyo-seed handles db.create_all() and default roles
        run_shopyo_command(["shopyo-seed"])
        
        # 2. Create Admin
        print("\n⚙️  Step 2/2: Creating admin credentials...")
        if not email:
            email = questionary.text("Admin Email:", default="admin@admin.com").ask()
        if not password:
            password = questionary.password("Admin Password:", default="admin").ask()
        
        # Final fallback for non-interactive without flags
        email = email or "admin@admin.com"
        password = password or "admin"
        
        run_shopyo_command(["shopyo-create-admin", email, password], quiet=True)
        
        console.print(Panel(
            f"[bold green]Setup Complete![/bold green]\n\n"
            f"📧  [bold]Email:[/bold]    {email}\n"
            f"🔑  [bold]Password:[/bold] [dim](hidden)[/dim]\n\n"
            f"You can now start the server with: [bold cyan]angel-claw serve[/bold cyan]",
            title="🪽 Angel Claw",
            border_style="green"
        ))
    elif len(sys.argv) > 1 and sys.argv[1] == "list-users":
        run_shopyo_command(["shopyo-list-users"])
    elif len(sys.argv) > 1 and sys.argv[1] == "bridges":
        ensure_env()
        print("🪽  Angel Claw Bridge Worker starting...")
        print("🤖 Telegram, WhatsApp, and Cron bridges active.")
        print("⏹️   Stop with Ctrl+C\n")

        async def run_all_bridges():
            from .telegram_bridge import telegram_bridge
            from .whatsapp_bridge import whatsapp_bridge
            from .cron import cron_manager

            lane_queue.start_workers()
            await asyncio.gather(
                telegram_bridge.run(), whatsapp_bridge.run(), cron_manager.run()
            )

        try:
            asyncio.run(run_all_bridges())
        except KeyboardInterrupt:
            pass
    elif len(sys.argv) > 1 and sys.argv[1] == "locate-static":
        app_static = importlib.resources.files("angel_claw").joinpath("app", "static")
        print(os.path.abspath(str(app_static)))
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
    elif len(sys.argv) == 1:
        # Default to starting the gateway if no subcommand
        start_gateway()
    else:
        print("🪽 Angel Claw CLI")
        print("Usage: angel-claw [chat|serve|tutorial|login-whatsapp|confirm-user|promote-user|create-admin|setup|list-users|bridges|locate-static|mcp]")


if __name__ == "__main__":
    main()
