from typing import AsyncGenerator, List, Dict
import anthropic
from .base import BaseLLM

class AnthropicLLM(BaseLLM):
    def __init__(self, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic()
        self.model = model

    async def stream_chat(
        self, 
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.messages.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            if chunk.type == "content_block_delta":
                yield chunk.delta.text

    async def chat(
        self, 
        messages: List[Dict[str, str]]
    ) -> str:
        response = await self.client.messages.create(
            model=self.model,
            messages=messages,
        )
        return response.content[0].text 