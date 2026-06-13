from typing import List, Dict, Any
from datetime import datetime
from memory.base import BaseMemory

class ShortTermMemory:
    # Grounding prompt instructing LLM to use web search for foreign timezones
    DEFAULT_SYSTEM_PROMPT = (
        "You are an advanced, real-time AI Assistant equipped with search and system tools.\n"
        "For any time-sensitive query, current event, or real-time fact, you MUST invoke the appropriate tool first. "
        "Do NOT attempt to answer real-time queries from your pre-trained memory.\n\n"
        "Grounding & Timezone Rules:\n"
        "1. To find the current date or time for a specific city or country outside of the host system, you MUST run a `search_web` query for 'current time in [location]'. "
        "Do not guess or run manual timezone math.\n"
        "2. Rely ONLY on the facts returned by your tools in the current session. Do not extrapolate or assume.\n"
        "3. You MUST cite your sources inline using descriptive markdown links: [Title of Source](URL).\n"
        "4. NEVER fabricate, hallucinate, or guess links, domains, or URLs (such as example.com). "
        "You are ONLY allowed to use URLs that are explicitly returned by your search tools in the current turn. "
        "If you did not execute a search tool, you must not output any markdown links."
    )

    def __init__(self, storage: BaseMemory, max_messages: int = 20, system_prompt: str | None = None):
        self.storage = storage
        self.max_messages = max_messages
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """Delegates persistent message saving to the database storage engine."""
        await self.storage.add_message(session_id, role, content, **kwargs)

    async def get_context(self, session_id: str) -> List[Dict[str, Any]]:
        """Loads historical messages, slices them to fit the token budget, and formats with system prompt containing the current date/time and host timezone."""
        raw_messages = await self.storage.get_messages(session_id)

        # Cap context window to recent messages
        recent_messages = raw_messages[-self.max_messages:] if self.max_messages > 0 else raw_messages

        # Dynamically retrieve and append current system time and timezone abbreviation to ground the LLM
        now = datetime.now()
        tz_name = now.astimezone().tzname()  # e.g., 'IST', 'EST', 'UTC'
        now_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
        dynamic_system_prompt = f"{self.system_prompt}\n\nCurrent System Date/Time: {now_str} ({tz_name})."

        # Build final system-injected list for LLM input
        context = [{"role": "system", "content": dynamic_system_prompt}]
        context.extend(recent_messages)

        return context

    async def clear(self, session_id: str) -> None:
        """Delegates chat history clearing to the database storage engine."""
        await self.storage.clear(session_id)