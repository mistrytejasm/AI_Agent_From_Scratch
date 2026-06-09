from abc import ABC, abstractmethod
from typing import AsyncGenerator

class BaseAgent(ABC):
    @abstractmethod
    async def run(self, session_id: str, user_input: str) -> str:
        """Processes user input and returns the complete agent response string."""
        pass

    @abstractmethod
    async def run_stream(self, session_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Processes user input and yields agent response tokens in real-time."""
        yield