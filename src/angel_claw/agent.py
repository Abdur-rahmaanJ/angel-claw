import litellm

from .models import Message, Role
from .memory import memory_manager
from .config import settings
from typing import List, Optional

class Agent:
    def __init__(self, session_id: str, model: str = None):
        self.session_id = session_id
        self.model = model or settings.model
        self.memos = memory_manager.get_memos(session_id)
        # Update memos model if overridden
        self.memos.reader.model = self.model
        self.soul = self._load_soul()

    def _load_soul(self) -> str:
        try:
            with open("SOUL.md", "r") as f:
                return f.read()
        except FileNotFoundError:
            return "You are Angel Claw, a helpful personal AI assistant."

    async def chat(self, user_input: str) -> str:
        # 1. Process memory (Retrieval)
        # Using a consistent user 'alice' for the CLI
        memory_context = self.memos.process(f"Retrieve context for: {user_input}", user="alice")
        
        # 2. Build messages
        system_prompt = (
            f"{self.soul}\n\n"
            "Use the following memory context to answer. "
            "IMPORTANT: Memories are listed from NEWEST to OLDEST. "
            "If there is conflicting information, ALWAYS trust the NEWEST memory.\n\n"
            f"Memory Context:\n{memory_context.get('response', 'No relevant memory found.')}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        # 3. Call LLM via litellm
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            api_key=settings.api_key
        )
        
        assistant_content = response.choices[0].message.content
        
        # 4. Store interaction in memory (Explicitly)
        # We use 'Remember:' to trigger storage even with fallback parser
        # And we store the fact directly for better retrieval later
        if any(trigger in user_input.lower() for trigger in ["i live in", "i am", "my name is", "i work at"]):
             self.memos.process(f"Remember: {user_input}", user="alice")
        else:
             self.memos.process(f"Remember: User said '{user_input}' and Assistant replied '{assistant_content}'", user="alice")
        
        return assistant_content
