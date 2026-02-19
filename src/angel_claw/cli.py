import asyncio
import uuid
import sys
import logging
import warnings
from .agent import Agent
from .config import settings
from .gateway import start as start_gateway
from .cron import cron_manager
from .telegram_bridge import telegram_bridge
from .whatsapp_bridge import whatsapp_bridge

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

async def interactive_chat(model: str = None):
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

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        model_override = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(interactive_chat(model_override))
    elif len(sys.argv) > 1 and sys.argv[1] == "login-whatsapp":
        from .whatsapp_bridge import whatsapp_bridge
        print("--- Angel Claw WhatsApp Login ---")
        print("Ensure WHATSAPP_ENABLED=True is set in your .env")
        # Force enable for this command
        whatsapp_bridge.enabled = True
        asyncio.run(whatsapp_bridge.run())
    else:
        # Default to starting the gateway if no subcommand or 'serve'
        start_gateway()

if __name__ == "__main__":
    main()
