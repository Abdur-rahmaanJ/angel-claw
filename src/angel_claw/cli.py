import asyncio
import uuid
import sys
from .agent import Agent
from .config import settings
from .gateway import start as start_gateway

async def interactive_chat(model: str = None):
    session_id = str(uuid.uuid4())
    agent = Agent(session_id, model=model)
    
    print(f"--- Angel Claw CLI Chat ---")
    print(f"Model: {agent.model}")
    print(f"Session: {session_id}")
    print("Type 'exit' or 'quit' to stop.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break
            if not user_input:
                continue
                
            print("Assistant: ", end="", flush=True)
            response = await agent.chat(user_input)
            print(response + "\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        model_override = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(interactive_chat(model_override))
    else:
        # Default to starting the gateway if no subcommand or 'serve'
        start_gateway()

if __name__ == "__main__":
    main()
