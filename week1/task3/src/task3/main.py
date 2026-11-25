import fastapi
import lmstudio as lms

from .models import ChatRequest, ChatResponse, Message, Session, SessionRequest

import json
import uuid
from datetime import datetime

from typing import List

app = fastapi.FastAPI()
model = lms.llm()

SERVER_API_HOST = "localhost:1234"

sessions = []

@app.get('/api/health')
def get_health():
    return {"status": "ok"}

@app.post('/sessions', response_model=Session)
async def create_session(request: SessionRequest) -> Session:
    new_session = Session(
        session_id=uuid.uuid4(),
        name=request.name,
        created_on= datetime.now(),
        messages=[]
    )
    sessions.append(new_session)
    return new_session

@app.get('/sessions')
async def get_sessions() -> List[Session]:
    return sessions

@app.post('/sessions/{session_id}/chat', response_model=ChatResponse)
def chat(session_id: uuid.UUID, request: ChatRequest) -> ChatResponse:
    target_session : Session = next((session for session in sessions if session.session_id==session_id), None)
    if target_session is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="session not found"
        )

    history = []

    for message in target_session.messages:
        content = (
            message.content.request
            if isinstance(message.content, ChatRequest)
            else message.content.response
        )
        history.append({"role": message.role, "content": content})

    history.append({"role": "user", "content": request.request})
    result = model.respond({"messages": history})
    result_dict = json.loads(result.content)
    response = ChatResponse.model_validate(result_dict)
    target_session.messages.extend([
        Message(role="user", content=request),
        Message(role="assistant", content=response)
    ])
    return ChatResponse.model_validate(result_dict)


