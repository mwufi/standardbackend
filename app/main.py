from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator, List
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime

from app.llm import AnthropicLLM

load_dotenv()

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = None

class Conversation(BaseModel):
    id: str
    messages: List[Message]
    started_at: datetime
    last_message_at: datetime = None
    total_messages: int = 0

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize
llm = AnthropicLLM()

# For streaming
conversations = {}  # Store conversations by ID
settings = {
    "systemPrompt": "You are a helpful AI assistant focused on providing clear and accurate information.",
    "personality": "friendly and professional",
    "hasMemory": True,
    "enabledTools": ["search", "code"]
}

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
    if chat_id not in conversations:
        # Initialize new conversation if it doesn't exist
        conversations[chat_id] = Conversation(
            id=chat_id,
            messages=[],
            started_at=datetime.now(),
            total_messages=0
        )
    return conversations[chat_id]

async def stream_response(chat_id: str) -> AsyncGenerator[str, None]:
    complete_response = ""
    conversation = conversations[chat_id]
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

@app.post("/chat/{chat_id}/push")
async def push_message(chat_id: str, request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    
    if chat_id not in conversations:
        conversations[chat_id] = Conversation(
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
    conversations[chat_id].messages.append(message)
    conversations[chat_id].total_messages += 1
    conversations[chat_id].last_message_at = datetime.now()

    return EventSourceResponse(
        stream_response(chat_id),
        media_type="text/event-stream"
    )