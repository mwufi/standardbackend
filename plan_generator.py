from pydantic import BaseModel, Field
from typing import List
import os
import json
from anthropic import Anthropic

# First, let's add our Pydantic models
class Step(BaseModel):
    action: str
    inputs: List[str]
    outputs: List[str]
    constraints: List[str] = Field(default_factory=list)

class ActionPattern(BaseModel):
    type: str
    frequency: str
    steps: List[Step]

class CurrentState(BaseModel):
    resources: dict = Field(default_factory=dict)
    constraints: dict = Field(default_factory=dict)
    progress_metrics: dict = Field(default_factory=dict)

class ExecutionStrategy(BaseModel):
    cycle: str
    checkpoints: List[str]
    memory_requirements: List[str]

class TaskPlan(BaseModel):
    goal: str
    success_metric: str
    current_state: CurrentState
    execution_strategy: ExecutionStrategy
    action_patterns: List[ActionPattern]

# Now let's fix the generate_task_plan function
def generate_task_plan(api_key: str, task_description: str) -> TaskPlan:
    client = Anthropic(api_key=api_key)
    
    task_plan_schema = TaskPlan.model_json_schema()
    
    tools = [
        {
            "name": "build_task_plan",
            "description": "Build a structured execution plan for any task with clear steps and requirements",
            "input_schema": task_plan_schema
        }
    ]

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1500,
        temperature=0.2,
        system="You are a task planning expert who breaks down complex tasks into detailed, actionable steps.",
        messages=[
            {
                "role": "user",
                "content": f"Create a detailed execution plan for the following task: {task_description}"
            }
        ],
        tools=tools,
        tool_choice={"type": "tool", "name": "build_task_plan"}
    )

    return TaskPlan(**message.content[0].input)

# Test it out with a single example first
if __name__ == "__main__":
    task = "Research and compile healthy vegetarian dinner recipes for a week"
    print(f"\nTask: {task}")
    print("-" * 50)
    plan = generate_task_plan(os.getenv("ANTHROPIC_API_KEY"), task)
    print(json.dumps(plan.model_dump(), indent=2))