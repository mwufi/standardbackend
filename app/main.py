from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, List
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import os

from app.llm import AnthropicLLM

load_dotenv()

# SQLite datetime adapter/converter
def adapt_datetime(dt: datetime) -> str:
    return dt.isoformat() if dt else None

def convert_datetime(s) -> datetime | None:
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    if isinstance(s, str):
        return datetime.fromisoformat(s)
    return None

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = None

class Conversation(BaseModel):
    id: str
    messages: List[Message]
    started_at: datetime
    last_message_at: datetime | None = None
    total_messages: int = 0

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
def init_db():
    db_path = "conversations.db"
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            started_at timestamp,
            last_message_at timestamp,
            total_messages INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            timestamp timestamp,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize
llm = AnthropicLLM()
init_db()

# Settings (kept in memory as it's small and frequently accessed)
settings = {
    "systemPrompt": "You are a helpful AI assistant focused on providing clear and accurate information.",
    "personality": "friendly and professional",
    "hasMemory": True,
    "enabledTools": ["search", "code"]
}

def get_db():
    return sqlite3.connect("conversations.db", detect_types=sqlite3.PARSE_DECLTYPES)

def save_conversation(conversation: Conversation, new_message: Message = None):
    conn = get_db()
    c = conn.cursor()
    
    # Update conversation metadata
    c.execute('''
        INSERT OR REPLACE INTO conversations (id, started_at, last_message_at, total_messages)
        VALUES (?, ?, ?, ?)
    ''', (
        conversation.id,
        conversation.started_at,
        conversation.last_message_at or datetime.now(),  # Ensure we never store None
        conversation.total_messages
    ))
    
    # If there's a new message, append it
    if new_message:
        c.execute('''
            INSERT INTO messages (conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (conversation.id, new_message.role, new_message.content, new_message.timestamp or datetime.now()))
    
    conn.commit()
    conn.close()

def load_conversation(chat_id: str) -> Conversation:
    conn = get_db()
    c = conn.cursor()
    
    # Get conversation
    c.execute('SELECT id, started_at, last_message_at, total_messages FROM conversations WHERE id = ?', (chat_id,))
    conv_row = c.fetchone()
    
    if not conv_row:
        conn.close()
        return None
    
    # Get messages
    c.execute('SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp', (chat_id,))
    messages = []
    for row in c.fetchall():
        timestamp = row[2]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        messages.append(Message(
            role=row[0],
            content=row[1],
            timestamp=timestamp or datetime.now()
        ))
    
    conn.close()

    # Convert datetime values
    started_at = conv_row[1]
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at)
    
    last_message_at = conv_row[2]
    if isinstance(last_message_at, str):
        last_message_at = datetime.fromisoformat(last_message_at)
    
    return Conversation(
        id=conv_row[0],
        started_at=started_at or datetime.now(),  # Ensure we never pass None
        last_message_at=last_message_at,
        total_messages=conv_row[3],
        messages=messages
    )

# Settings routes
@app.get("/settings")
async def get_settings():
    return settings

@app.post("/settings")
async def update_settings(request: Request):
    data = await request.json()
    settings.update(data)
    return settings

@app.get("/chat/{chat_id}")
async def get_conversation(chat_id: str):
    conversation = load_conversation(chat_id)
    if not conversation:
        # Initialize new conversation if it doesn't exist
        conversation = Conversation(
            id=chat_id,
            messages=[],
            started_at=datetime.now(),
            total_messages=0
        )
        save_conversation(conversation)
    return conversation

async def stream_response(chat_id: str) -> AsyncGenerator[str, None]:
    complete_response = ""
    conversation = load_conversation(chat_id)
    messages_for_llm = [{"role": m.role, "content": m.content} for m in conversation.messages]
    
    async for chunk in llm.stream_chat(messages_for_llm):
        complete_response += chunk
        print(chunk)
        yield {"data": json.dumps({"content": chunk})}

    message = Message(
        role="assistant",
        content=complete_response,
        timestamp=datetime.now()
    )
    conversation.messages.append(message)
    conversation.total_messages += 1
    conversation.last_message_at = datetime.now()
    save_conversation(conversation, message)

@app.post("/chat/{chat_id}/push")
async def push_message(chat_id: str, request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    
    conversation = load_conversation(chat_id)
    if not conversation:
        conversation = Conversation(
            id=chat_id,
            messages=[],
            started_at=datetime.now(),
            total_messages=0
        )
    
    message = Message(
        role="user",
        content=user_message,
        timestamp=datetime.now()
    )
    conversation.messages.append(message)
    conversation.total_messages += 1
    conversation.last_message_at = datetime.now()
    save_conversation(conversation, message)

    return EventSourceResponse(
        stream_response(chat_id),
        media_type="text/event-stream"
    )