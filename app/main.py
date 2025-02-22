from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from datetime import datetime
import json
from typing import Dict, Set, Callable, Any
import traceback
import asyncio
from contextlib import asynccontextmanager

from .config import get_settings
from .database.db import Database
from .database.models import Message, Conversation
from .services.llm.anthropic import AnthropicLLM

from dotenv import load_dotenv

load_dotenv()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, chat_id: str):
        """Add a websocket connection to a chat room"""
        if chat_id not in self.active_connections:
            self.active_connections[chat_id] = set()
        self.active_connections[chat_id].add(websocket)
        await self.broadcast_json(chat_id, {
            "type": "connect",
            "chat_id": chat_id,
            "timestamp": datetime.utcnow().isoformat()
        })

    def disconnect(self, websocket: WebSocket, chat_id: str):
        """Remove a websocket connection from a chat room"""
        if chat_id in self.active_connections:
            self.active_connections[chat_id].discard(websocket)
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]

    async def switch_room(self, websocket: WebSocket, old_chat_id: str | None, new_chat_id: str):
        """Switch a websocket connection from one chat room to another"""
        if old_chat_id:
            self.disconnect(websocket, old_chat_id)
            await self.broadcast_json(old_chat_id, {
                "type": "disconnect",
                "chat_id": old_chat_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        await self.connect(websocket, new_chat_id)

    async def broadcast_json(self, chat_id: str, message: dict):
        """Broadcast a message to all connections in a chat room"""
        if chat_id in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[chat_id]:
                try:
                    await connection.send_json(message)
                except RuntimeError:
                    dead_connections.add(connection)
            
            # Clean up dead connections
            for dead in dead_connections:
                self.active_connections[chat_id].discard(dead)
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]

    async def broadcast_error(self, chat_id: str, error: str, details: str = None):
        """Broadcast an error message to all clients in a chat room"""
        await self.broadcast_json(chat_id, {
            "type": "error",
            "error": error,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })

@asynccontextmanager
async def websocket_error_handler(websocket: WebSocket, chat_id: str, manager: ConnectionManager):
    """Context manager for handling WebSocket errors"""
    try:
        yield
    except WebSocketDisconnect:
        manager.disconnect(websocket, chat_id)
        await manager.broadcast_json(chat_id, {
            "type": "disconnect",
            "chat_id": chat_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        # Get the full traceback
        error_details = traceback.format_exc()
        print(f"WebSocket Error: {str(e)}\n{error_details}")
        
        try:
            # Try to notify clients of the error
            await manager.broadcast_error(
                chat_id,
                str(e),
                error_details if app.debug else None
            )
        except:
            pass  # If error broadcasting fails, we don't want to crash
        finally:
            # Always ensure we disconnect on error
            manager.disconnect(websocket, chat_id)

app = FastAPI()
app.debug = True  # Set to False in production
settings = get_settings()
db = Database(settings.database_url)
llm = AnthropicLLM(model=settings.llm_model)
manager = ConnectionManager()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/settings")
async def get_app_settings():
    return {
        "systemPrompt": settings.system_prompt,
        "personality": settings.personality,
        "hasMemory": settings.has_memory,
        "enabledTools": settings.enabled_tools
    }

@app.post("/settings")
async def update_app_settings(request: Request):
    data = await request.json()
    # In a production app, you'd want to validate and persist these settings
    return data

@app.get("/chat/{chat_id}")
async def get_conversation(chat_id: str):
    conversation = db.load_conversation(chat_id)
    if not conversation:
        conversation = Conversation(
            id=chat_id,
            started_at=datetime.utcnow(),
            total_messages=0
        )
        db.save_conversation(conversation)
    return conversation

async def stream_response(chat_id: str):
    complete_response = ""
    conversation = db.load_conversation(chat_id)
    messages_for_llm = [{"role": m.role, "content": m.content} for m in conversation.messages]
    
    async for chunk in llm.stream_chat(messages_for_llm):
        complete_response += chunk
        yield {"data": json.dumps({"content": chunk})}

    message = Message(
        role="assistant",
        content=complete_response,
        timestamp=datetime.utcnow()
    )
    conversation.messages.append(message)
    conversation.total_messages += 1
    conversation.last_message_at = datetime.utcnow()
    db.save_conversation(conversation, message)

@app.post("/chat/{chat_id}/push")
async def push_message(chat_id: str, request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    
    conversation = db.load_conversation(chat_id)
    if not conversation:
        conversation = Conversation(
            id=chat_id,
            started_at=datetime.utcnow(),
            total_messages=0
        )
    
    message = Message(
        role="user",
        content=user_message,
        timestamp=datetime.utcnow()
    )
    conversation.messages.append(message)
    conversation.total_messages += 1
    conversation.last_message_at = datetime.utcnow()
    db.save_conversation(conversation, message)

    return EventSourceResponse(
        stream_response(chat_id),
        media_type="text/event-stream"
    ) 

@app.websocket("/v2/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()  # Accept the connection once at the start
    chat_id = None
    
    try:
        # Set up tool callback
        async def tool_callback(event: dict):
            try:
                if chat_id:
                    await manager.broadcast_json(chat_id, event)
            except RuntimeError:
                pass  # Connection already closed
        
        llm.set_tool_callback(tool_callback)
        
        while True:
            try:
                data = await websocket.receive_json()
                if isinstance(data, str):
                    data = json.loads(data)
                
                # Get chat_id from the message
                new_chat_id = data.get("chat_id")
                if not new_chat_id:
                    await websocket.send_json({
                        "type": "error",
                        "error": "No chat_id provided",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    continue
                
                # Handle chat switching
                if data.get("type") == "switch_chat":
                    await manager.switch_room(websocket, chat_id, new_chat_id)
                    chat_id = new_chat_id
                    continue
                
                # Ensure chat_id matches current chat
                if new_chat_id != chat_id:
                    await manager.switch_room(websocket, chat_id, new_chat_id)
                    chat_id = new_chat_id

                if data.get("type") == "convo-reset":
                    # Clear conversation in DB
                    db.clear(chat_id)
                    
                    await manager.broadcast_json(chat_id, {
                        "type": "convo-reset",
                        "chat_id": chat_id,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                elif data.get("type") == "message":
                    user_message = data.get("content", "")
                    if not user_message.strip():
                        await manager.broadcast_error(chat_id, "Empty message received")
                        continue

                    conversation = db.load_conversation(chat_id)
                    if not conversation:
                        conversation = Conversation(
                            id=chat_id,
                            started_at=datetime.utcnow(),
                            total_messages=0
                        )
                    
                    # Send agent joined event
                    await manager.broadcast_json(chat_id, {
                        "type": "agent_joined",
                        "agent_id": "assistant",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    message = Message(
                        role="user",
                        content=user_message,
                        timestamp=datetime.utcnow()
                    )
                    conversation.messages.append(message)
                    conversation.total_messages += 1
                    conversation.last_message_at = datetime.utcnow()
                    db.save_conversation(conversation, message)

                    # Send message received confirmation
                    await manager.broadcast_json(chat_id, {
                        "type": "message_received",
                        "content": user_message,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                    # Stream the response
                    complete_response = ""
                    messages_for_llm = [{"role": m.role, "content": m.content} for m in conversation.messages]
                    
                    async for chunk in llm.stream_chat(messages_for_llm):
                        complete_response += chunk
                        await manager.broadcast_json(chat_id, {
                            "type": "text_delta",
                            "delta": chunk,
                            "timestamp": datetime.utcnow().isoformat()
                        })

                    # Save the assistant's message
                    message = Message(
                        role="assistant",
                        content=complete_response,
                        timestamp=datetime.utcnow()
                    )
                    conversation.messages.append(message)
                    conversation.total_messages += 1
                    conversation.last_message_at = datetime.utcnow()
                    db.save_conversation(conversation, message)
                    
                    # Send agent left event
                    await manager.broadcast_json(chat_id, {
                        "type": "agent_left",
                        "agent_id": "assistant", 
                        "timestamp": datetime.utcnow().isoformat()
                    })
            except WebSocketDisconnect:
                if chat_id:
                    manager.disconnect(websocket, chat_id)
                break
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON message received",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue
            except Exception as e:
                error_details = traceback.format_exc()
                print(f"Error processing message: {str(e)}\n{error_details}")
                if chat_id:
                    await manager.broadcast_error(
                        chat_id,
                        f"Error processing message: {str(e)}",
                        error_details if app.debug else None
                    )
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"WebSocket error: {str(e)}\n{error_details}")
        if chat_id:
            manager.disconnect(websocket, chat_id)

@app.get("/chats")
async def get_all_chats():
    """Get all conversations with their latest message."""
    with db.get_connection() as conn:
        c = conn.cursor()
        
        # Get all conversations with their latest message
        c.execute('''
            SELECT 
                c.id, 
                c.started_at as "started_at [timestamp]",
                c.last_message_at as "last_message_at [timestamp]",
                c.total_messages,
                m.content as latest_message
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE m.id = (
                SELECT id FROM messages 
                WHERE conversation_id = c.id 
                ORDER BY timestamp DESC 
                LIMIT 1
            )
            ORDER BY c.last_message_at DESC
        ''')
        
        chats = [{
            'id': row[0],
            'started_at': row[1].isoformat() if row[1] else None,
            'last_message_at': row[2].isoformat() if row[2] else None,
            'total_messages': row[3],
            'latest_message': row[4] or ''
        } for row in c.fetchall()]
        
        return chats 