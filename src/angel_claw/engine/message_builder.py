import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger("angel-claw-engine-msgbuilder")


class MessageBuilder:
    """Builds messages for LLM calls."""

    MAX_RECENT_HISTORY = 5

    def __init__(self, settings):
        self._settings = settings

    def build_system_prompt(
        self, runtime, context, user_id: str, safe_memory: str
    ) -> str:
        """Build the system prompt with soul, user info, and memory context."""
        return (
            f"{runtime.soul}\n\n"
            f"CURRENT USER: {context.email} (ID: {user_id})\n"
            f"CHANNEL: {context.channel_type} ({context.channel_identifier})\n\n"
            "--- BEGIN RETRIEVED MEMORY CONTEXT ---\n"
            f"{safe_memory}\n"
            "--- END RETRIEVED MEMORY CONTEXT ---\n\n"
            "You have access to 'Skills' which are sandboxed tools you can call. "
            "Always validate tool outputs before using them in your response."
        )

    def build_streaming_system_prompt(
        self, runtime, context, user_id: str, safe_memory: str
    ) -> str:
        """Build the system prompt for streaming mode."""
        from datetime import datetime, UTC

        return (
            f"{runtime.soul}\n\n"
            f"CURRENT USER: {context.email} (ID: {user_id})\n"
            f"CHANNEL: {context.channel_type} ({context.channel_identifier})\n\n"
            "--- BEGIN RETRIEVED MEMORY CONTEXT ---\n"
            f"{safe_memory}\n"
            "--- END RETRIEVED MEMORY CONTEXT ---\n\n"
            f"Current date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

    def build_messages(
        self, system_prompt: str, recent_history: List, message: str
    ) -> List[Dict[str, Any]]:
        """Build message list for LLM."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend([m.model_dump(exclude_none=True) for m in recent_history])
        messages.append({"role": "user", "content": message})
        return messages

    def build_messages_from_list(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert message list to simple dict format."""
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def extract_recursion_depth(self, message: str) -> int:
        """Extract recursion depth from message if present."""
        depth_match = re.search(r"\[RECURSION_DEPTH: (\d+)\]", message)
        return int(depth_match.group(1)) if depth_match else 0


class MemoryRetriever:
    """Retrieves and formats memory context."""

    MAX_RESULTS = 5

    def retrieve(self, memos, context, session_id: str, use_global: bool):
        """Retrieve memory cubes."""
        if use_global:
            return memos.operator.hybrid_retrieve(
                query="",  # Will be replaced by caller
                user=context.email,
                namespace=None,
                n_results=self.MAX_RESULTS,
            )

        user_namespace = f"user_{context.email}"
        ns_to_check = [
            session_id,
            f"{session_id}_logs",
            user_namespace,
            f"{user_namespace}_logs",
            "default",
        ]

        all_collected_ids = set()
        for ns in ns_to_check:
            all_collected_ids.update(memos.vault.namespaces.get(ns, set()))

        retrieved_cubes = [memos.vault.get(cid) for cid in all_collected_ids]
        retrieved_cubes = [c for c in retrieved_cubes if c and c.owner == context.email]
        retrieved_cubes.sort(key=lambda c: c.timestamp, reverse=True)
        return retrieved_cubes[: self.MAX_RESULTS]

    def format_memory_context(self, retrieved_cubes, memos) -> str:
        """Format retrieved cubes into memory context string."""
        if not retrieved_cubes:
            return "No relevant memory found."

        snippets = [
            f"• [{c.timestamp.strftime('%Y-%m-%d %H:%M')}] [{c.semantic_type.value.upper()}] {memos.api._format_payload(c.payload, 150)}"
            for c in retrieved_cubes
        ]
        return "Memory Context (Prioritized & Newest First):\n" + "\n".join(snippets)

    def sanitize_memory(self, raw_memory: str) -> str:
        """Sanitize memory to prevent injection attacks."""
        return raw_memory.replace("---", " - ")


def create_message_builder(settings) -> MessageBuilder:
    return MessageBuilder(settings)


def create_memory_retriever() -> MemoryRetriever:
    return MemoryRetriever()
