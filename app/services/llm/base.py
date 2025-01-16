from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any

class BaseLLM(ABC):
    @abstractmethod
    async def stream_chat(
        self, 
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Stream a chat response from the LLM."""
        pass

    @abstractmethod
    async def chat(
        self, 
        messages: List[Dict[str, str]]
    ) -> str:
        """Get a complete chat response from the LLM."""
        pass 