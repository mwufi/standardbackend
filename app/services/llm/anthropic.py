from typing import AsyncGenerator, List, Dict, Optional, Callable
import anthropic
from .base import BaseLLM
import json
from datetime import datetime

class AnthropicLLM(BaseLLM):
    def __init__(self, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.tool_callback: Optional[Callable[[Dict], None]] = None

    def set_tool_callback(self, callback: Callable[[Dict], None]):
        self.tool_callback = callback

    async def stream_chat(
        self, 
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        # must have max-tokens set
        stream = await self.client.messages.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            if chunk.type == "content_block_delta":
                yield chunk.delta.text
            elif chunk.type == "tool_calls" and self.tool_callback:
                for tool_call in chunk.delta.tool_calls:
                    await self.tool_callback({
                        "type": "tool_use_called",
                        "name": tool_call.type,
                        "id": tool_call.id,
                        "args": tool_call.parameters,
                        "timestamp": datetime.utcnow().isoformat()
                    })

    async def chat(
        self, 
        messages: List[Dict[str, str]]
    ) -> str:
        response = await self.client.messages.create(
            model=self.model,
            messages=messages,
        )
        return response.content[0].text 