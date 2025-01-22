from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging
import random
import string
import asyncio
import uuid

from app.agent import Agent
from app.llm import AnthropicLLM
from app.socks import WebSocketManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# tools
from standardbackend.tools.base import Tool
from pydantic import BaseModel


class WeatherInput(BaseModel):
    location: str

    @staticmethod
    def execute(data):
        print("executing tool", data)
        return "the weather is nice"


tools = [
    Tool(
        name="get_weather",
        description="Get the weather for a given location",
        input_schema=WeatherInput,
        execute=WeatherInput.execute,
    )
]

g = Agent()
llm = AnthropicLLM(tools=tools)
socks = WebSocketManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await socks.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await socks.handle_message(websocket, message)
    except WebSocketDisconnect:
        socks.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        socks.disconnect(websocket)


# Register message handlers
@socks.handle("user_message")
async def handle_user_message(data: Any, websocket: WebSocket):
    if data["isNewConversation"]:
        g.clear_messages()
    g.add_message(data["content"])
    complete_response = ""
    async for chunk in llm.stream_chat(g.system_prompt, g.build_messages()):
        if chunk.type == "text":
            complete_response += chunk.content
            await websocket.send_json(
                {
                    "type": "text_delta",
                    "delta": chunk.content,
                }
            )
        elif chunk.type == "tool_use":
            print("tool use", chunk)
            await websocket.send_json(
                {
                    "type": "tool_use",
                    "id": chunk.content.id,
                    "tool": chunk.content.name,
                    "input": chunk.content.input,
                }
            )
        else:
            print("unknown chunk type", chunk)

    g.add_message(complete_response, role="assistant")
    return None


@socks.handle("a")
async def handle_a(data: Any, websocket: WebSocket):
    return {"type": "pong"}


@socks.handle("b")
async def handle_b(data: Any, websocket: WebSocket):
    for _ in range(15):
        random_string = "".join(random.choices(string.ascii_letters, k=5))
        await websocket.send_json({"type": "text_delta", "data": random_string})
    return None


@socks.handle("c")
async def handle_c(data: Any, websocket: WebSocket):
    message_id = str(uuid.uuid4())
    await websocket.send_json({"type": "start", "id": message_id})

    async def send_delayed_stop():
        await asyncio.sleep(3)
        await websocket.send_json({"type": "stop", "id": message_id})

    asyncio.create_task(send_delayed_stop())
    return None


@socks.handle("set_system_prompt")
async def handle_set_system_prompt(data: Any, websocket: WebSocket):
    print("setting system prompt", data)
    g.set_system_prompt(data)
    return None


@socks.handle("clear_messages")
async def handle_clear_messages(data: Any, websocket: WebSocket):
    g.clear_messages()
    return {"type": "clear_messages"}


@socks.on_connect
async def handle_connect(websocket: WebSocket):
    """Send initial state to client on connection"""
    return {
        "type": "initial_state",
        "data": {"messages": g.build_messages(), "system_prompt": g.system_prompt},
    }


@app.get("/chat")
async def get_chat():
    r = {"messages": g.build_messages(), "system_prompt": g.system_prompt}
    print(r)
    return r
