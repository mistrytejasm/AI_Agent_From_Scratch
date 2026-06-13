from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List

class BaseLLM(ABC):
    @abstractmethod
    async def generate(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> Dict[str, Any]:
        """Generates a complete response (text or tool calls) from the LLM asynchronously."""
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]] | None = None, **kwargs) -> AsyncGenerator[str, None]:
        """Streams text response tokens in real-time from the LLM asynchronously."""
        yield