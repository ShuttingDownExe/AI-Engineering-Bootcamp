from pydantic import BaseModel, Field
from typing import Literal, List
import uuid
from datetime import datetime

class ChatRequest(BaseModel):
    request: str

class ChatResponse(BaseModel):
    intent: Literal["general_question", "domain_question", "action_request", "unclear"]
    response: str
    confidence: float= Field(ge=0.0, le=1.0)
    sources_needed: bool

class Message(BaseModel):
    role: Literal["assistant", "user"]
    content: ChatRequest | ChatResponse

class SessionRequest(BaseModel):
    name: str

class Session(BaseModel):
    session_id: uuid.UUID
    name: str
    created_on: datetime
    messages: List[Message]