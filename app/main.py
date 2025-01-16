from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from datetime import datetime
import json

from .config import get_settings
from .database.db import Database
from .database.models import Message, Conversation
from .services.llm.anthropic import AnthropicLLM

from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
settings = get_settings()
db = Database(settings.database_url)
llm = AnthropicLLM(model=settings.llm_model)

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