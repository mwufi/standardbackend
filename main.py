from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, Type
import openai
import os
from dotenv import load_dotenv
import time
import base64
from datetime import datetime
from schemas import MathReasoning

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Track server start time
SERVER_START_TIME = time.time()

app = FastAPI(title="OpenAI GPT-4 Completion Service")


class Message(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]], None] = None
    audio: Optional[Dict[str, str]] = None


class CompletionRequest(BaseModel):
    messages: List[Message]
    response_format: Optional[Dict[str, Any]] = None
    modalities: Optional[List[str]] = None
    audio: Optional[Dict[str, str]] = None


@app.get("/models")
async def list_models():
    try:
        models = client.models.list()
        return {"models": [model.id for model in models]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/uptime")
async def get_uptime():
    uptime_seconds = time.time() - SERVER_START_TIME
    return {
        "uptime_seconds": uptime_seconds,
        "started_at": datetime.fromtimestamp(SERVER_START_TIME).isoformat(),
        "current_time": datetime.now().isoformat(),
    }


@app.post("/completion")
async def create_completion(request: CompletionRequest):
    """Basic text completion endpoint"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": msg.role, "content": msg.content} for msg in request.messages
            ],
            response_format=request.response_format,
        )

        return {
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "finish_reason": response.choices[0].finish_reason,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/math")
async def solve_math(request: CompletionRequest):
    """Math problem solving endpoint with step-by-step reasoning"""
    try:
        # Add system message if not present
        messages = request.messages
        if not any(msg.role == "system" for msg in messages):
            messages = [
                Message(
                    role="system",
                    content="You are a helpful math tutor. Guide the user through the solution step by step.",
                )
            ] + messages

        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": msg.role, "content": msg.content} for msg in messages],
            response_format=MathReasoning,
        )

        return {
            "result": completion.choices[0].message.parsed,
            "role": completion.choices[0].message.role,
            "finish_reason": completion.choices[0].finish_reason,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/audio/completion")
async def create_audio_completion(request: CompletionRequest):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-audio-preview-2024-10-01",
            modalities=request.modalities or ["text", "audio"],
            audio=request.audio or {"voice": "alloy", "format": "wav"},
            messages=[
                {
                    "role": msg.role,
                    "content": msg.content,
                    "audio": msg.audio,
                }
                for msg in request.messages
            ],
        )

        response_data = {
            "index": 0,
            "message": {
                "role": completion.choices[0].message.role,
                "content": completion.choices[0].message.content,
                "refusal": None,
            },
            "finish_reason": completion.choices[0].finish_reason,
        }

        # Add audio data if present
        if hasattr(completion.choices[0].message, "audio"):
            audio = completion.choices[0].message.audio
            response_data["message"]["audio"] = {
                "id": audio.id,
                "expires_at": audio.expires_at,
                "data": audio.data,
                "transcript": audio.transcript,
            }

        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
