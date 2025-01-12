from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from standardbackend.tools.base import Tool


class ExecutionStatus(Enum):
    """Status of a tool execution"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionResult:
    """Result of a tool execution"""

    status: ExecutionStatus
    result: Optional[str] = None
    error: Optional[str] = None


class ToolCache:
    """A helper class that knows how to cache tool results"""

    def __init__(self, tools: List[Tool]):
        self.cache: Dict[str, ExecutionResult] = {}
        self.tools = tools or []
        self.tool_name_to_tool = {tool.name: tool for tool in tools}
        self.tool_specs = [tool.to_dict() for tool in tools]

    def get(self, execution_id: str) -> Optional[ExecutionResult]:
        """Get the result of a tool execution by ID"""
        ans = self.cache.get(execution_id)

        # for now, make sure the result is a string!
        if ans and ans.result:
            ans.result = str(ans.result)

        return ans

    def _lookup_tool(self, tool_name: str) -> Tool:
        """Lookup a tool by name"""
        if tool_name in self.tool_name_to_tool:
            return self.tool_name_to_tool[tool_name]
        raise ValueError(f"Tool {tool_name} not found")

    def request_execution(
        self, execution_id: str, tool_name: str, input: dict
    ) -> ExecutionResult:
        """Request execution of a tool

        Args:
            execution_id: Unique ID for this execution
            tool_name: Name of the tool to execute
            input: Input parameters for the tool

        Returns:
            ExecutionResult containing status and result/error
        """
        if execution_id in self.cache:
            return self.cache[execution_id]

        try:
            # Mark as running
            self.cache[execution_id] = ExecutionResult(status=ExecutionStatus.RUNNING)

            # Execute the tool
            real_tool = self._lookup_tool(tool_name)
            formatted_input = real_tool.input_schema(**input)
            result = real_tool.execute(formatted_input)

            # Store successful result
            execution_result = ExecutionResult(
                status=ExecutionStatus.COMPLETED, result=result
            )

        except Exception as e:
            # Store failed result
            execution_result = ExecutionResult(
                status=ExecutionStatus.FAILED, error=str(e)
            )

        self.cache[execution_id] = execution_result
        return execution_result
