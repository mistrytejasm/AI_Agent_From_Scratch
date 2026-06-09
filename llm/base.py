from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List

class BaseLLM(ABC):
    @abstractmethod
    async def generate(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Generates a complete text response from the LLM asynchronously."""
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[str, None]:
        """Streams text response tokens in real-time from the LLM asynchronously."""
        # Using yield inside an async method forms an async generator
        yield
        
