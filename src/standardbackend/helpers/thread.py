from anthropic import Anthropic
import os
from standardbackend.tools import ExecutionStatus, ToolCache
from standardbackend.tools.python_code_runner import tools as python_tools


class Thread:
    """Represents a conversation thread with Claude that can use tools"""

    def __init__(
        self, model="claude-3-haiku-20240307", temperature=0.2, max_tokens=1200
    ):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.tool_cache = ToolCache(python_tools)
        self.messages = []
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _parse_message(self, message):
        """Parse Claude's message and handle any tool calls"""
        metadata = {"tools_called": []}
        tool_responses = []

        def handle_text_output(block):
            print(block.text)

        def handle_tool_use(block):
            print(f"[tool_use] {block.name} {block.id}")
            print("=> ", block.input)

            # Schedule execution - right now it executes immediately
            ans = self.tool_cache.request_execution(block.id, block.name, block.input)

            # Get the result!
            ans = self.tool_cache.get(block.id)

            if ans.status == ExecutionStatus.COMPLETED:
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
                print(f"Tool {block.id} failed with error: {ans.error}")

            print(f"[tool_answer] {ans.result}")

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

    def send_message(self, message: str) -> list:
        """Send a message to Claude and handle the response"""
        self.add_message("user", message)

        claude_message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            tools=self.tool_cache.tool_specs,
            tool_choice={"type": "auto"},
            messages=self.messages,
        )

        metadata, tool_responses = self._parse_message(claude_message)

        # Add Claude's response and any tool responses to the conversation
        self.messages.append(claude_message)
        self.messages.extend(tool_responses)

        return self.messages


# Example usage:
