from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator
import json
from dotenv import load_dotenv

from app.llm import AnthropicLLM

load_dotenv()

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
messages = []

async def stream_response() -> AsyncGenerator[str, None]:
    complete_response = ""
    async for chunk in llm.stream_chat(messages):
        complete_response += chunk
        print(chunk)
        yield {"data": json.dumps({"content": chunk})}

    messages.append({"role": "assistant", "content": complete_response})


@app.post("/chat/{chat_id}/push")
async def push_message(chat_id: str, request: Request):
    data = await request.json()
    user_message = data.get("message", "")
    messages.append({"role": "user", "content": user_message})

    return EventSourceResponse(
        stream_response(),
        media_type="text/event-stream"
    )