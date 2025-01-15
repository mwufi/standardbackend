from typing import List, Dict, AsyncGenerator, Optional
import anthropic
from anthropic.types import Message, MessageParam


class AnthropicLLM:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()
        self.model = model

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response from Anthropic's Claude
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            
        Yields:
            Streamed response text chunks
        """
        async with self.client.messages.stream(
            max_tokens=max_tokens,
            messages=messages,
            model=self.model,
            temperature=temperature,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Get a complete chat response (non-streaming)
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            
        Returns:
            Complete response text
        """
        response = await self.client.messages.create(
            max_tokens=max_tokens,
            messages=messages,
            model=self.model,
            temperature=temperature,
        )
        
        return response.content[0].text
