from pydantic import BaseModel

import uuid

class ChatRequest(BaseModel):
    message: str

class AttachFilesRequest(BaseModel):
    file_ids: list[uuid.UUID]