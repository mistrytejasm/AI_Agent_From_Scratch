from typing import List, Dict, Any
from memory.base import BaseMemory

class ShortTermMemory:
    def __init__(self, storage: BaseMemory, max_messages: int = 20, system_prompt: str | None = None):
        self.storage = storage
        self.max_messages = max_messages
        self.system_prompt = system_prompt or "You are helpful AI Assistant."

    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """Delegates persistent message saving to the database storage engine."""
        await self.storage.add_message(session_id, role, content, **kwargs)

    async def get_context(self, session_id: str) -> List[Dict[str, Any]]:
        """Loads historical messages, slices them to fit the token budget, and formats with system prompt."""
        raw_messages = await self.storage.get_messages(session_id)

        # Cap context window to recent messages
        recent_messages = raw_messages[-self.max_messages:] if self.max_messages > 0 else raw_messages

        # Build final system-injected list for LLM input
        context = [{"role": "system", "content": self.system_prompt}]
        context.extend(recent_messages)

        return context

    async def clear(self, session_id: str) -> None:
        """Delegates chat history clearing to the database storage engine."""
        await self.storage.clear(session_id)

