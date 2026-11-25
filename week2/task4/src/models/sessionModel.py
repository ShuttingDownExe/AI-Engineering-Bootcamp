from pydantic import BaseModel, Field
from typing import List, Literal
from uuid import UUID, uuid4
from datetime import datetime


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    persona: Literal["system", "assistant", "user"]
    content: str
    time: datetime
    reasoning: str = ""

class SessionRequest(BaseModel):
    name: str

class Session(BaseModel):
    id: UUID
    name: str
    messages: List[Message]

