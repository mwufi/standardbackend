import anthropic
from anthropic.types import ToolUseBlock
from typing import List, Dict, AsyncGenerator, Optional
from dataclasses import dataclass
from typing import Union

# Define a tool that takes in a task description and returns a task plan
from standardbackend.tools.base import Tool
from pydantic import BaseModel
from standardbackend.tools.cache import ToolCache


@dataclass
class AsyncGeneratorResult:
    """Represents a result from the async generator stream"""

    type: str  # Can be 'text' or 'tool_use'
    content: Union[str, dict]  # Either text content or tool result dictionary


class AnthropicLLM:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-latest",
        tools: List[Tool] = [],
    ):
        self.client = (
            anthropic.AsyncAnthropic(api_key=api_key)
            if api_key
            else anthropic.AsyncAnthropic()
        )
        self.model = model
        self.tools = tools
        self.tool_cache = ToolCache(tools)

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: List[Tool] = [],
    ) -> AsyncGenerator[AsyncGeneratorResult, None]:
        """
        Handles streaming events from the Anthropic API

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)

        Yields:
            Streamed response text chunks
        """
        print(system_prompt, messages)

        def handle_streaming_tool_use(block: ToolUseBlock):
            self.tool_cache.request_execution(block.id, block.name, block.input)
            return AsyncGeneratorResult(type="tool_use", content=block)

        def handle_streaming_text_end(text: str):
            pass

        def handle_streaming_text_partial(text_delta: str):
            return AsyncGeneratorResult(type="text", content=text_delta)

        def handle_streaming_tool_use_partial(partial_json):
            pass

        def unhandled_event(event):
            pass

        def process_event(event):
            if event.type == "message_start":
                pass
            elif event.type == "content_block_start":
                pass
            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    return handle_streaming_text_partial(delta.text)
                elif delta.type == "input_json_delta":
                    return handle_streaming_tool_use_partial(delta.partial_json)
                else:
                    unhandled_event(event)
            elif event.type == "content_block_stop":
                content_block = event.content_block
                if content_block.type == "text":
                    return handle_streaming_text_end(content_block.text)
                elif content_block.type == "tool_use":
                    return handle_streaming_tool_use(content_block)
                else:
                    unhandled_event(event)
            else:
                unhandled_event(event)

        async with self.client.messages.stream(
            max_tokens=max_tokens,
            messages=messages,
            system=system_prompt,
            model=self.model,
            temperature=temperature,
            tools=self.tool_cache.tool_specs,
        ) as stream:
            async for event in stream:
                processed_event = process_event(event)
                if processed_event:
                    yield processed_event
                else:
                    continue

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
