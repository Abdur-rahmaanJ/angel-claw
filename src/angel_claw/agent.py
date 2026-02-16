import litellm
from .models import Message, Role
from .memory import memory_manager
from .config import settings
from typing import List

class Agent:
    def __init__(self, session_id: str, model: str = None):
        self.session_id = session_id
        self.model = model or settings.model
        self.memos = memory_manager.get_memos(session_id)
        # Update memos model if overridden
        self.memos.reader.model = self.model
        
    async def chat(self, user_input: str) -> str:
        # 1. Process memory (Retrieval)
        # In angel-recall, memos.process() handles both storage and retrieval 
        # based on the content. We can call it to get context.
        memory_context = self.memos.process(f"Retrieve context for: {user_input}")
        
        # 2. Build messages
        system_prompt = (
            "You are Angel Claw, a helpful personal AI assistant. "
            "Use the following memory context if relevant:
"
            f"{memory_context.get('response', 'No relevant memory found.')}"
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
        
        # 4. Store interaction in memory (Implicitly)
        # We can store the fact that this interaction happened or let memos.process decide
        self.memos.process(f"User said: {user_input}
Assistant said: {assistant_content}")
        
        return assistant_content
