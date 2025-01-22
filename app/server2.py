from typing import Dict, Callable, Any, Optional, List, NamedTuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
from dataclasses import dataclass
import random
import string
import asyncio
import uuid
import time

from app.agent import Agent
from app.llm import AnthropicLLM

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketMessage:
    type: str
    data: Any


class HeartbeatHandler(NamedTuple):
    handler: Callable
    interval: float  # in seconds
    last_beat: float = 0.0  # timestamp of last heartbeat


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_handlers: Dict[str, Callable] = {}
        self.heartbeat_handlers: List[HeartbeatHandler] = []
        self.heartbeat_task = None
        self.base_heartbeat_interval = 1.0  # Check handlers every second

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

        # Start heartbeat task if this is the first connection
        if self.heartbeat_task is None:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"Client disconnected. Total connections: {len(self.active_connections)}"
            )

            # Cancel heartbeat task if no more connections
            if len(self.active_connections) == 0 and self.heartbeat_task:
                self.heartbeat_task.cancel()
                self.heartbeat_task = None
        else:
            logger.warning("Client not found in active connections")

    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")

    def register_heartbeat_handler(self, handler: Callable, interval: float):
        """Register a handler that will be called on its specified interval

        Args:
            handler: Async function that returns dict of data to send
            interval: How often to call this handler (in seconds)
        """
        self.heartbeat_handlers.append(
            HeartbeatHandler(handler=handler, interval=interval, last_beat=0.0)
        )
        logger.info(f"Registered new heartbeat handler with {interval}s interval")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        if message.get("type") == "heartbeat":
            logger.debug(
                f"Broadcasting heartbeat to {len(self.active_connections)} clients: {message}"
            )
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to client: {str(e)}")

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

    async def _heartbeat_loop(self):
        """Background task that triggers heartbeat handlers on their intervals"""
        logger.info("Starting heartbeat loop")
        try:
            while True:
                await asyncio.sleep(self.base_heartbeat_interval)
                if self.active_connections:
                    current_time = time.time()
                    heartbeat_data = {}

                    # Check each handler
                    for i, handler_info in enumerate(self.heartbeat_handlers):
                        time_since_last = current_time - handler_info.last_beat
                        if time_since_last >= handler_info.interval:
                            logger.debug(
                                f"Running heartbeat handler {i} after {time_since_last:.1f}s"
                            )
                            try:
                                result = await handler_info.handler()
                                if result:
                                    heartbeat_data.update(result)
                                # Update last beat time
                                self.heartbeat_handlers[i] = handler_info._replace(
                                    last_beat=current_time
                                )
                            except Exception as e:
                                logger.error(f"Error in heartbeat handler: {str(e)}")

                    # Only send if we have data
                    if heartbeat_data:
                        await self.broadcast(
                            {
                                "type": "heartbeat",
                                "data": heartbeat_data,
                                "timestamp": current_time,
                            }
                        )
                else:
                    logger.debug("No active connections, skipping heartbeat")
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {str(e)}")
            if self.active_connections:
                logger.info("Restarting heartbeat loop")
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())


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

g = Agent()
llm = AnthropicLLM()
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
    await manager.connect(
        websocket
    )  # This will handle accept() and register the connection

    try:
        while True:
            message = await websocket.receive_text()
            await manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)


# Example of how to register handlers:
async def handle_user_message(data: Any, websocket: WebSocket):
    g.add_message(data)
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


async def handle_set_system_prompt(data: Any, websocket: WebSocket):
    g.set_system_prompt(data)
    return None


# Register your handlers
manager.register_handler("user_message", handle_user_message)
manager.register_handler("a", handle_a)
manager.register_handler("b", handle_b)
manager.register_handler("c", handle_c)
manager.register_handler("set_system_prompt", handle_set_system_prompt)


# Example heartbeat handlers with different intervals
async def agent_sync_handler():
    return {"agent": {"messages": g.build_messages(), "system_prompt": g.system_prompt}}


async def connection_stats_handler():
    return {"stats": {"connected_clients": len(manager.active_connections)}}


# Register handlers with different intervals
manager.register_heartbeat_handler(agent_sync_handler, interval=3.0)  # Every 3 seconds
manager.register_heartbeat_handler(
    connection_stats_handler, interval=5.0
)  # Every 5 seconds
