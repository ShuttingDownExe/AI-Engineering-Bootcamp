import fastapi
import lmstudio as lms
model = lms.llm()
from pydantic import BaseModel

app = fastapi.FastAPI()

SERVER_API_HOST = "localhost:1234"

class ChatRequest(BaseModel):
    request: str

class ChatResponse(BaseModel):
    response: str


@app.get('/api/health')
def get_health():
    return {"status": "ok"}

@app.post('/api/chat')
async def chat(request: ChatRequest) -> ChatResponse:
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant. Answer clearly and concisely. If you don't know then say so"
        },
        {
            "role": "user",
            "content": request.request
        }
    ]
    result = model.respond({"messages": messages})
    return ChatResponse(response=result.content)
