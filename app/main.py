from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator
import asyncio
import json

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def stream_response(message: str) -> AsyncGenerator[str, None]:
    # Simulate streaming response (replace with actual OpenAI streaming)
    words = message.split()
    for word in words:
        yield {"data": json.dumps({"content": word + " "})}
        await asyncio.sleep(0.2)  # Simulate delay

@app.post("/chat/{chat_id}/push")
async def push_message(chat_id: str, request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    
    return EventSourceResponse(
        stream_response(user_message),
        media_type="text/event-stream"
    )