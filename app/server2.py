from typing import Dict, Callable, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
from dataclasses import dataclass
import random
import string
import asyncio
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketMessage:
    type: str
    data: Any


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_handlers: Dict[str, Callable] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(
            f"Client disconnected. Total connections: {len(self.active_connections)}"
        )

    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        for connection in self.active_connections:
            await connection.send_json(message)

    async def handle_message(self, websocket: WebSocket, message_data: str):
        """Handle incoming WebSocket messages"""
        try:
            message = json.loads(message_data)
            if not isinstance(message, dict) or "type" not in message:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": "Invalid message format. Expected {type: string, data: any}",
                    }
                )
                return

            message_type = message["type"]
            handler = self.message_handlers.get(message_type)

            if handler:
                response = await handler(message.get("data"), websocket)
                print("\033[92m" + "->", response, "\033[0m")
                if response:
                    await websocket.send_json(response)
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": f"No handler registered for message type: {message_type}",
                    }
                )

        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "data": "Invalid JSON message"})
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await websocket.send_json(
                {"type": "error", "data": f"Internal server error: {str(e)}"}
            )


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "ws://localhost:3000",
        "ws://127.0.0.1:3000",
        "ws://localhost:8000",
        "ws://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

# Add origins configuration for WebSocket
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "ws://localhost:3000",
    "ws://127.0.0.1:3000",
    "ws://localhost:8000",
    "ws://127.0.0.1:8000",
]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()  # Accept the connection first

    try:
        while True:
            message = await websocket.receive_text()
            await manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)


from app.agent import Agent
from app.llm import AnthropicLLM

g = Agent()
llm = AnthropicLLM()


# Example of how to register handlers:
async def handle_user_message(data: Any, websocket: WebSocket):
    g.add_message(data)
    complete_response = ""
    async for chunk in llm.stream_chat(g.build_messages()):
        if chunk.type == "text":
            complete_response += chunk.content
            await websocket.send_json(
                {
                    "type": "text_delta",
                    "delta": chunk.content,
                }
            )
        elif chunk.type == "tool_use":
            print(chunk)

    g.add_message(complete_response, role="assistant")
    return None


async def handle_a(data: Any, websocket: WebSocket):
    return {"type": "pong"}


async def handle_b(data: Any, websocket: WebSocket):
    for _ in range(15):
        random_string = "".join(random.choices(string.ascii_letters, k=5))
        await websocket.send_json({"type": "text_delta", "data": random_string})
    return None  # No final response needed since we sent multiple responses


async def handle_c(data: Any, websocket: WebSocket):
    message_id = str(uuid.uuid4())
    await websocket.send_json({"type": "start", "id": message_id})

    async def send_delayed_stop():
        await asyncio.sleep(3)
        await websocket.send_json({"type": "stop", "id": message_id})

    # Create background task
    asyncio.create_task(send_delayed_stop())

    # Return None since we're handling the responses directly
    return None


# Register your handlers
manager.register_handler("user_message", handle_user_message)
manager.register_handler("a", handle_a)
manager.register_handler("b", handle_b)
manager.register_handler("c", handle_c)
