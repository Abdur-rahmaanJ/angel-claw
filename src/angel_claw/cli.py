import asyncio
import uuid
import sys
from .agent import Agent
from .config import settings
from .gateway import start as start_gateway
from .cron import cron_manager
from .telegram_bridge import telegram_bridge
from .whatsapp_bridge import whatsapp_bridge

async def interactive_chat(model: str = None):
    # Start background workers
    cron_task = asyncio.create_task(cron_manager.run())
    telegram_task = asyncio.create_task(telegram_bridge.run())
    whatsapp_task = asyncio.create_task(whatsapp_bridge.run())
    
    # Give background tasks a moment to initialize before we start blocking with input()
    await asyncio.sleep(1)
    
    # Use a persistent session ID for CLI by default
    session_id = "cli-default"
    agent = Agent(session_id, model=model)
    
    print(f"--- Angel Claw CLI Chat ---")
    print(f"Model: {agent.model}")
    print(f"Session: {session_id}")
    print("Type 'exit' or 'quit' to stop.\n")
    
    while True:
        try:
            # Use to_thread to keep the event loop running for background tasks while waiting for input
            user_input = await asyncio.to_thread(input, "You: ")
            user_input = user_input.strip()
            if user_input.lower() in ["exit", "quit"]:
                break
            if not user_input:
                continue
                
            print("Assistant: ", end="", flush=True)
            # Use asyncio for chat as it is async
            response = await agent.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")
    
    # Cancel the cron worker task
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass

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
