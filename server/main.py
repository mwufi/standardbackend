from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from thread_backend import ThreadBackend
from pydantic import create_model

app = FastAPI()
backend = ThreadBackend()


class CreateAgentRequest(BaseModel):
    name: str
    system_prompt: str


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None


class CreateThreadRequest(BaseModel):
    agent_id: str
    title: str


class AddMessageRequest(BaseModel):
    content: str
    agent_id: Optional[str] = None


class CreateToolRequest(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class UpdateToolRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None


class AssignToolRequest(BaseModel):
    tool_id: str


@app.post("/agents")
async def create_agent(request: CreateAgentRequest):
    agent = backend.create_agent(request.name, request.system_prompt)
    return agent


@app.put("/agents/{agent_id}")
async def update_agent(agent_id: str, request: UpdateAgentRequest):
    try:
        agent = backend.update_agent(agent_id, request.name, request.system_prompt)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/threads")
async def create_thread(request: CreateThreadRequest):
    try:
        thread = backend.create_thread(request.agent_id, request.title)
        return thread
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/threads/{thread_id}/messages")
async def add_message(thread_id: str, request: AddMessageRequest):
    try:
        message = backend.add_message(thread_id, request.content, request.agent_id)
        return message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    try:
        messages = backend.get_thread_messages(thread_id)
        return messages
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tools")
async def create_tool(request: CreateToolRequest):
    schema_model = create_model(
        "DynamicSchema",
        **{
            field_name: (eval(field_info.get("type", "str")), ...)
            for field_name, field_info in request.input_schema.get(
                "properties", {}
            ).items()
        },
    )
    tool = backend.create_tool(request.name, request.description, schema_model)
    return tool


@app.put("/tools/{tool_id}")
async def update_tool(tool_id: str, request: UpdateToolRequest):
    try:
        schema_model = None
        if request.input_schema:
            schema_model = create_model(
                "DynamicSchema",
                **{
                    field_name: (eval(field_info.get("type", "str")), ...)
                    for field_name, field_info in request.input_schema.get(
                        "properties", {}
                    ).items()
                },
            )
        tool = backend.update_tool(
            tool_id, request.name, request.description, schema_model
        )
        return tool
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/agents/{agent_id}/tools")
async def assign_tool_to_agent(agent_id: str, request: AssignToolRequest):
    try:
        backend.assign_tool_to_agent(agent_id, request.tool_id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/agents/{agent_id}/tools")
async def get_agent_tools(agent_id: str):
    try:
        tools = backend.get_agent_tools(agent_id)
        return tools
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/agents/{agent_id}/threads")
async def get_agent_threads(agent_id: str):
    try:
        threads = backend.get_agent_threads(agent_id)
        return threads
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
