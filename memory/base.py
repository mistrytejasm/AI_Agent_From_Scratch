from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseMemory(ABC):
    @abstractmethod
    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """Saves a message to persistent storage asynchronously."""
        pass

    @abstractmethod
    async def get_messages(self, session_id: str, **kwargs) -> List[Dict[str, Any]]:
        """Retrieves messages for a session in chat completion dict format asynchronously."""
        pass
    
    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Clears all message history associated with a session asynchronously."""
        pass