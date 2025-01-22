from typing import Dict, Callable, Any, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
import logging
import json
from dataclasses import dataclass, field

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketManager:
    """A clean, reusable WebSocket manager for FastAPI applications."""

    # Store active connections
    active_connections: List[WebSocket] = field(default_factory=list)

    # Store message handlers
    _handlers: Dict[str, Callable] = field(default_factory=dict)

    # Store connection handlers
    _on_connect_handler: Optional[Callable] = None
    _on_disconnect_handler: Optional[Callable] = None

    def handle(self, message_type: str):
        """Decorator to register a handler for a specific message type."""

        def decorator(handler: Callable):
            self._handlers[message_type] = handler
            logger.info(f"Registered handler for message type: {message_type}")
            return handler

        return decorator

    def on_connect(self, handler: Callable):
        """Decorator to register a connection handler."""
        self._on_connect_handler = handler
        return handler

    def on_disconnect(self, handler: Callable):
        """Decorator to register a disconnection handler."""
        self._on_disconnect_handler = handler
        return handler

    @property
    def routes(self) -> Dict[str, Callable]:
        """Get all registered message handlers."""
        return self._handlers

    async def connect(self, websocket: WebSocket):
        """Handle new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

        if self._on_connect_handler:
            response = await self._on_connect_handler(websocket)
            if response:
                await websocket.send_json(response)

    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"Client disconnected. Total connections: {len(self.active_connections)}"
            )

            if self._on_disconnect_handler:
                self._on_disconnect_handler(websocket)
        else:
            logger.warning("Client not found in active connections")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to client: {str(e)}")

    async def handle_message(self, websocket: WebSocket, message_data: str):
        """Handle incoming WebSocket messages."""
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
            handler = self._handlers.get(message_type)

            if handler:
                response = await handler(message.get("data"), websocket)
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
