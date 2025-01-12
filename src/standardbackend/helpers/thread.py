from anthropic import Anthropic
import os
import logging
from standardbackend.tools import ExecutionStatus, ToolCache
from standardbackend.tools.python_code_runner import tools as python_tools

from dotenv import load_dotenv

# Just load the .env file by default
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


def _default_tool_use_callback(block):
    print(f"[tool_use] {block.name} {block.id}")
    print("=> ", block.input)


def _default_text_callback(block):
    print(block.text)


class Thread:
    """Represents a conversation thread with Claude that can use tools"""

    def __init__(
        self,
        model="claude-3-haiku-20240307",
        temperature=0.2,
        max_tokens=1200,
        tools=None,
        on_text_callback=None,
        on_tool_use_callback=None,
    ):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.tool_cache = ToolCache(tools)
        self.messages = []
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # optional callbacks
        # "default" - print to console
        # None - no callback
        # function - call the function
        self.on_text_callback = on_text_callback
        self.on_tool_use_callback = on_tool_use_callback

    def _parse_message(self, message):
        """Parse Claude's message and handle any tool calls"""
        metadata = {"tools_called": []}
        tool_responses = []

        def handle_text_output(block):
            if self.on_text_callback == "default":
                _default_text_callback(block)
            elif self.on_text_callback is not None:
                self.on_text_callback(block)

        def handle_tool_use(block):
            logger.info(f"Tool called: {block.name} (ID: {block.id})")
            logger.debug(f"Tool input: {block.input}")

            if self.on_tool_use_callback == "default":
                _default_tool_use_callback(block)
            elif self.on_tool_use_callback is not None:
                self.on_tool_use_callback(block)

            try:
                # Schedule execution - right now it executes immediately
                ans = self.tool_cache.request_execution(
                    block.id, block.name, block.input
                )

                # Get the result!
                ans = self.tool_cache.get(block.id)

                if ans.status == ExecutionStatus.COMPLETED:
                    logger.info(f"Tool {block.id} completed successfully")
                    logger.debug(f"Tool result: {ans.result}")
                    tool_responses.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": ans.result,
                                }
                            ],
                        }
                    )
                else:
                    error_msg = f"Tool {block.id} failed with error: {ans.error}"
                    logger.error(error_msg)
                    tool_responses.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": f"Error: {ans.error}",
                                }
                            ],
                        }
                    )
            except Exception as e:
                error_msg = f"Tool {block.id} failed with unexpected error: {str(e)}"
                logger.error(error_msg)
                tool_responses.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {str(e)}",
                            }
                        ],
                    }
                )

        for block in message.content:
            content_type = block.type
            if content_type == "text":
                handle_text_output(block)
            elif content_type == "tool_use":
                handle_tool_use(block)
                metadata["tools_called"].append(block.id)
            else:
                raise ValueError(f"Unexpected message type: {content_type}")

        return metadata, tool_responses

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

        claude_message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            tools=self.tool_cache.tool_specs,
            tool_choice={"type": tool_mode},
            messages=self.messages,
        )

        metadata, tool_responses = self._parse_message(claude_message)

        # Add Claude's response and any tool responses to the conversation
        self.messages.append({"role": "assistant", "content": claude_message.content})
        self.messages.extend(tool_responses)

        while claude_message.stop_reason == "tool_use":
            claude_message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                tools=self.tool_cache.tool_specs,
                tool_choice={"type": "auto"},
                messages=self.messages,
            )
            metadata, tool_responses = self._parse_message(claude_message)
            self.messages.append(
                {"role": "assistant", "content": claude_message.content}
            )
            self.messages.extend(tool_responses)

        return self.messages
