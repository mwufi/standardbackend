from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    id: str
    messages: List[Message] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: Optional[datetime] = None
    total_messages: int = 0 