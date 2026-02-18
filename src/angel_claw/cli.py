import asyncio
import uuid
import sys
from .agent import Agent
from .config import settings
from .gateway import start as start_gateway
from .cron import cron_manager
from .telegram_bridge import telegram_bridge

async def interactive_chat(model: str = None):
    # Start background workers
    cron_task = asyncio.create_task(cron_manager.run())
    telegram_task = asyncio.create_task(telegram_bridge.run())
    
    # Use a persistent session ID for CLI by default
    session_id = "cli-default"
    agent = Agent(session_id, model=model)
    
    print(f"--- Angel Claw CLI Chat ---")
    print(f"Model: {agent.model}")
    print(f"Session: {session_id}")
    print("Type 'exit' or 'quit' to stop.\n")
    
    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(None, input, "You: ")
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
    else:
        # Default to starting the gateway if no subcommand or 'serve'
        start_gateway()

if __name__ == "__main__":
    main()
