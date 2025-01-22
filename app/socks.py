from typing import Dict, Callable, Any, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import logging
import json
from dataclasses import dataclass, field
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WebSocketManager:
    """A clean, reusable WebSocket manager for FastAPI applications."""

    # Store active connections (using a set for O(1) lookups)
    active_connections: Set[WebSocket] = field(default_factory=set)

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
        self.active_connections.add(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

        if self._on_connect_handler:
            response = await self._on_connect_handler(websocket)
            if response:
                await websocket.send_json(response)

    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        try:
            self.active_connections.remove(websocket)
            logger.info(
                f"Client disconnected. Total connections: {len(self.active_connections)}"
            )

            if self._on_disconnect_handler:
                self._on_disconnect_handler(websocket)
        except KeyError:
            logger.warning("Client not found in active connections")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients concurrently."""
        # Create tasks for all sends
        tasks = [
            asyncio.create_task(self._safe_send(connection, message))
            for connection in self.active_connections
        ]

        # Wait for all sends to complete
        if tasks:
            await asyncio.gather(*tasks)

    async def _safe_send(self, websocket: WebSocket, message: dict):
        """Safely send a message to a single websocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to client: {str(e)}")
            # Optionally disconnect problematic clients
            self.disconnect(websocket)

    async def handle_message(self, websocket: WebSocket, message_data: str):
        """Handle incoming WebSocket messages."""
        try:
            # Parse message once
            try:
                message = json.loads(message_data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "data": "Invalid JSON message"}
                )
                return

            # Validate message structure
            if not isinstance(message, dict):
                await websocket.send_json(
                    {"type": "error", "data": "Message must be a JSON object"}
                )
                return

            message_type = message.get("type")
            if not message_type:
                await websocket.send_json(
                    {"type": "error", "data": "Message must have a 'type' field"}
                )
                return

            # Get handler (O(1) dictionary lookup)
            handler = self._handlers.get(message_type)
            if not handler:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": f"No handler registered for message type: {message_type}",
                    }
                )
                return

            # Execute handler with data
            response = await handler(message.get("data"), websocket)
            if response:
                await websocket.send_json(response)

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await websocket.send_json(
                {"type": "error", "data": f"Internal server error: {str(e)}"}
            )
