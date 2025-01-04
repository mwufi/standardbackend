from enum import Enum
from typing import List
from pydantic import BaseModel


class Step(BaseModel):
    explanation: str
    output: str


class MathReasoning(BaseModel):
    steps: List[Step]
    final_answer: str


# Add more structured output schemas as needed
