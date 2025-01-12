from typing import Optional, List
import subprocess
import tempfile
import os
import signal
from contextlib import contextmanager
from pydantic import BaseModel

from standardbackend.tools.base import Tool


class EvalInput(BaseModel):
    code: str
    timeout: Optional[int] = 30
    max_output_length: Optional[int] = 1000


@contextmanager
def timeout(seconds):
    def signal_handler(signum, frame):
        raise TimeoutError("Code execution timed out")

    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


def execute_python_code(input_data: EvalInput) -> str:
    """Execute Python code in a temporary file with timeout and output limits.

    Args:
        input_data (EvalInput): Contains code to execute, optional timeout and max output length

    Returns:
        str: Output from code execution, including stdout and stderr

    Raises:
        TimeoutError: If code execution exceeds timeout
        Exception: For any other execution errors
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(input_data.code)
        temp_file = f.name

    try:
        with timeout(input_data.timeout):
            result = subprocess.run(
                ["python", temp_file],
                capture_output=True,
                text=True,
                timeout=input_data.timeout,
            )

        output = result.stdout + result.stderr
        if input_data.max_output_length:
            output = output[: input_data.max_output_length]

        return output

    except TimeoutError:
        return "Code execution timed out"
    except Exception as e:
        return f"Error executing code: {str(e)}"
    finally:
        os.unlink(temp_file)


# export a default list of tools :)
tools: List[Tool] = [
    Tool(
        name="run_python_code",
        description="Run Python code with configurable timeout and output limits",
        input_schema=EvalInput,
        execute=execute_python_code,
    )
]

python_tool = Tool(
    name="run_python_code",
    description="Run Python code with configurable timeout and output limits",
    input_schema=EvalInput,
    execute=execute_python_code,
)
