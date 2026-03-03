import asyncio
import sys
import uuid
import questionary
from .config import settings
from .lane_queue.process import process_chat_request
from .lane_queue.queue import lane_queue
from .cron import cron_manager
from .models import AgentRequest

async def run_tutorial():
    print("\n🎓 Welcome to the Angel Claw Tutorial! 🎓")
    print("This guided tour will show you how to use memory, scheduling, and skills.\n")

    # Start background workers for the tutorial
    lane_queue.start_workers()
    cron_task = asyncio.create_task(cron_manager.run())

    # Register CLI proactive handler for the tutorial
    def tutorial_proactive_handler(message: str, user_id: str, session_id: str):
        if session_id.startswith("tutorial-"):
            print(f"\r\n🔔 [Tutorial Notification] {message}")
            print("You: ", end="", flush=True)

    cron_manager.register_proactive_handler(tutorial_proactive_handler)

    session_id = f"tutorial-{uuid.uuid4().hex[:8]}"
    
    # 1. Memory
    print("--- Step 1: Memory ---")
    print("Angel Claw has long-term memory. It remembers facts across sessions.")
    print("👉 Type: 'Remember that I love hiking.'")
    
    user_input = await asyncio.to_thread(input, "You: ")
    print("Thinking...", end="\r", flush=True)
    request = AgentRequest(session_id=session_id, message=user_input, user_id="tutorial-user")
    response = await process_chat_request(request)
    print(f"Assistant: {response}\n")

    print("Now verify it. 👉 Type: 'What do I like doing?'")
    user_input = await asyncio.to_thread(input, "You: ")
    print("Thinking...", end="\r", flush=True)
    request = AgentRequest(session_id=session_id, message=user_input, user_id="tutorial-user")
    response = await process_chat_request(request)
    print(f"Assistant: {response}\n")

    # 2. Scheduling
    print("--- Step 2: Scheduling ---")
    print("Angel Claw can set reminders and schedule recurring tasks.")
    print("👉 Type: 'Remind me to stretch in 5 seconds.'")
    
    user_input = await asyncio.to_thread(input, "You: ")
    print("Thinking...", end="\r", flush=True)
    request = AgentRequest(session_id=session_id, message=user_input, user_id="tutorial-user")
    response = await process_chat_request(request)
    print(f"Assistant: {response}\n")
    
    print("Waiting for the reminder... (5 seconds)")
    await asyncio.sleep(6) 
    print("")

    # 3. Skill Generation
    print("--- Step 3: Skill Generation ---")
    print("Angel Claw can create its own tools (skills) in Python.")
    print("👉 Type: 'Create a skill that tells me a random color.'")
    
    user_input = await asyncio.to_thread(input, "You: ")
    print("Thinking... (this may take a moment as the agent writes code)", end="\r", flush=True)
    request = AgentRequest(session_id=session_id, message=user_input, user_id="tutorial-user")
    response = await process_chat_request(request)
    print(f"Assistant: {response}\n")

    print("Now use your new skill. 👉 Type: 'Tell me a random color.'")
    user_input = await asyncio.to_thread(input, "You: ")
    print("Thinking...", end="\r", flush=True)
    request = AgentRequest(session_id=session_id, message=user_input, user_id="tutorial-user")
    response = await process_chat_request(request)
    print(f"Assistant: {response}\n")

    print("🎉 Tutorial complete!")
    print("You've seen Memory, Scheduling, and Skill Generation in action.")
    print("Run 'angel-claw chat' to start your own session.")

    # Cleanup
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass
