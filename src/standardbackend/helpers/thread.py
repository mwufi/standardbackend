from anthropic import Anthropic, AsyncAnthropic
import os
import logging
from standardbackend.tools import ExecutionStatus, ToolCache
from standardbackend.tools.python_code_runner import tools as python_tools
import asyncio
from typing import AsyncGenerator, Union, Dict, Any

from dotenv import load_dotenv

# Just load the .env file by default
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


class Thread:
    """Represents a conversation thread with Claude that can use tools"""

    def __init__(
        self,
        model="claude-3-haiku-20240307",
        temperature=0.2,
        max_tokens=1200,
        tools=None,
        agent=None,
        on_text_callback=None,
        on_tool_use_callback=None,
    ):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.tool_cache = ToolCache(tools) if tools else None
        self.messages = []
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.on_text_callback = on_text_callback
        self.on_tool_use_callback = on_tool_use_callback
        self.tools = tools
        self.agent = agent

    def _handle_text_output(self, block):
        """Handle text output from Claude with optional callback"""
        if self.on_text_callback is not None:
            self.on_text_callback(block)

    def _handle_tool_callback(self, block):
        """Handle tool use callback if configured"""
        logger.info(f"Tool {block.id} | {block.name} | {block.input}")

        if self.on_tool_use_callback is not None:
            self.on_tool_use_callback(block)

    def _execute_tool(self, block):
        """Execute a tool and return the response message"""
        try:
            # Schedule and execute tool
            self.tool_cache.request_execution(block.id, block.name, block.input)
            result = self.tool_cache.get(block.id)

            if result.status == ExecutionStatus.COMPLETED:
                logger.info(
                    f"Tool {block.id} completed successfully. Result: {result.result}"
                )
                return self._create_tool_response(block.id, result.result)
            else:
                logger.error(f"Tool {block.id} failed with error: {result.error}")
                return self._create_tool_response(block.id, f"Error: {result.error}")

        except Exception as e:
            logger.error(f"Tool {block.id} failed with unexpected error: {str(e)}")
            return self._create_tool_response(block.id, f"Error: {str(e)}")

    def _create_tool_response(self, tool_id, content):
        """Create a standardized tool response message"""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": content,
                }
            ],
        }

    def _parse_message(self, message):
        """Parse Claude's message and handle any tool calls"""
        metadata = {"tools_called": []}
        tool_responses = []

        for block in message.content:
            if block.type == "text":
                self._handle_text_output(block)
            elif block.type == "tool_use":
                self._handle_tool_callback(block)
                metadata["tools_called"].append(block.id)
                tool_responses.append(self._execute_tool(block))
            else:
                raise ValueError(f"Unexpected message type: {block.type}")

        return metadata, tool_responses

    def _blocks_to_dict(self, blocks):
        """Converts TextBlock and ToolUseBlock to dicts"""
        t = []
        for block in blocks:
            t.append(block.to_dict())
        return t

    def add_message(self, role: str, content: str):
        """Add a message to the conversation"""
        self.messages.append({"role": role, "content": content})

    def send_message(self, message: str, tool_mode: str = "auto") -> list:
        """Send a message to Claude and handle the response

        Args:
            message: The message to send to Claude
            tool_mode: One of "auto", "any", or "tool". Controls how Claude uses tools:
                - "auto": Claude decides whether to use tools (default)
                - "any": Claude must use one of the provided tools
        """
        self.add_message("user", message)

        while True:
            tool_args = (
                {
                    "tools": self.tool_cache.tool_specs,
                    "tool_choice": {"type": tool_mode},
                }
                if self.tools
                else {}
            )

            model_args = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            system_prompt = (
                {
                    "system": self.agent.get_current_context(),
                }
                if self.agent
                else {}
            )

            message_args = {
                "messages": self.messages,
                **model_args,
                **tool_args,
                **system_prompt,
            }

            claude_message = self.client.messages.create(**message_args)
            metadata, tool_responses = self._parse_message(claude_message)
            self.add_message("assistant", self._blocks_to_dict(claude_message.content))
            self.messages.extend(tool_responses)

            if claude_message.stop_reason != "tool_use":
                break
            tool_mode = "auto"  # Switch to auto mode for follow-up messages

        return self.messages

    async def send_message_stream(self, message: str, tool_mode: str = "auto") -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Send a message to Claude and stream the response with tool handling

        Args:
            message: The message to send to Claude
            tool_mode: One of "auto", "any", or "tool". Controls how Claude uses tools:
                - "auto": Claude decides whether to use tools (default)
                - "any": Claude must use one of the provided tools

        Yields:
            Either a string chunk of text from Claude or a dictionary containing tool results
        """
        self.add_message("user", message)

        while True:
            tool_args = (
                {
                    "tools": self.tool_cache.tool_specs,
                    "tool_choice": {"type": tool_mode},
                }
                if self.tools
                else {}
            )

            model_args = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            system_prompt = (
                {
                    "system": self.agent.get_current_context(),
                }
                if self.agent
                else {}
            )

            message_args = {
                "messages": self.messages,
                **model_args,
                **tool_args,
                **system_prompt,
            }

            async with self.client.messages.stream(**message_args) as stream:
                message_content = []
                async for message_delta in stream:
                    for block in message_delta.content:
                        if block.type == "text":
                            if self.on_text_callback is not None:
                                self.on_text_callback(block)
                            yield block.text
                            message_content.append(block)
                        elif block.type == "tool_use":
                            if self.on_tool_use_callback is not None:
                                self.on_tool_use_callback(block)
                            tool_response = self._execute_tool(block)
                            yield {"tool_result": tool_response}
                            self.messages.append(tool_response)
                            message_content.append(block)

                self.add_message("assistant", message_content)

                if stream.stop_reason != "tool_use":
                    break
                tool_mode = "auto"  # Switch to auto mode for follow-up messages
