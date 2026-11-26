from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Query
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient
from starlette.concurrency import run_in_threadpool
import aiofiles
import httpx2

from openai import AsyncOpenAI

from dotenv import load_dotenv, find_dotenv

from typing import List
from pydantic import BaseModel
from pathlib import Path

from .models.requestModel import ChatRequest, AttachFilesRequest
from .models.sessionModel import Session, Message

from .services.extraction import extract_pages, chunk_pages

import os
import uuid
from datetime import datetime
import json
import asyncio
import re

MAX_FILE_SIZE = 50 *1024 *1024
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"]
)

load_dotenv(find_dotenv())

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL")
API_KEY = os.getenv("API_KEY")
MODEL = "google/gemma-4-e2b"


client = AsyncOpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY")
)

session_store : List[Session] = []
session_files: dict[uuid.UUID, list[dict]] = {}
uploads: dict[uuid.UUID, dict] = {}
file_chunks: dict[uuid.UUID, list[dict]] = {}

@app.post("/session")
async def create_session() -> Session:
    session = Session(
        id=uuid.uuid4(),
        name="temp-name",
        messages=[]
    )
    session_store.append(session)
    return session

class sessionListItem(BaseModel):
    id: uuid.UUID
    name: str

@app.get("/session")
async def get_sessions() -> List[sessionListItem]:
    session_ids = []
    for session in session_store:
        session_ids.append(sessionListItem(id=session.id, name=session.name))
    return session_ids

__SESSION_NAME_PROMPT = """
Write a concise title for this conversation.
Use 3 to 6 words. Return only the title, without quotation marks.
"""

async def generate_title(session: Session, first_prompt: str):
    try:
        async with httpx2.AsyncClient(timeout=60.0) as http:
            response = await http.post(
                LMSTUDIO_BASE_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}"
                },
                json={
                    "model": MODEL,
                    "system_prompt": __SESSION_NAME_PROMPT,
                    "input": first_prompt,
                    "reasoning": "off",
                    "stream": False,
                    "store": False,
                    "max_output_tokens": 64,
                }
            )
            response.raise_for_status()

        result = response.json()

        title = "".join(
            item["content"]
            for item in result["output"]
            if item["type"] == "message"
        ).strip()

        if title:
            session.name = title
    except Exception:
        print("TITLE GENERATION ERROR")

def search_chunks(
    session_id: uuid.UUID,
    question: str,
    limit: int = 4
) -> list[dict]:
    question_words = set(re.findall(r"\w+", question.lower()))

    candidates = [
        chunk
        for chunks in file_chunks.values()
        for chunk in chunks
        if chunk["session_id"] == session_id
    ]

    def score(chunk: dict) -> int:
        chunk_words = set(re.findall(r"\w+", chunk["content"].lower()))
        return len(question_words & chunk_words)

    return sorted(candidates, key=score, reverse=True)[:limit]

async def llm_stream_chunk(session: Session):
    title_task = None

    if len(session.messages) == 1:
        title_task = asyncio.create_task(
            generate_title(
                session=session,
                first_prompt=session.messages[0].content,
            )
        )

    question = session.messages[-1].content
    relevant_chunks = search_chunks(session_id=session.id, question=question)

    document_context = "\n\n".join(
        f"[Source: {chunk["filename"]}, page: {chunk["page"]}]\n"
        f"{chunk['content']}"
        for chunk in relevant_chunks
    )

    try:
        history = [
            {
                "role": "system",
                "content": (
                    "Use the document excerpts below when the answer the user's question. If the excerpts do not antain the answer, say so. If there are no documents, or if the excerpts do not sufficiently answer the question just proceed with what you know.\n\n"
                    f"Document Excerpts: {document_context}"
                )
            },
            *[
                {"role": message.persona, "content": message.content}
                for message in session.messages
            ]
        ]

        stream = await client.chat.completions.create(
            model=MODEL,
            messages=history,
            stream=True,
        )

        response_parts = []
        reasoning_parts = []

        async for chunk in stream:
            # Check without blocking answer generation.
            if title_task is not None and title_task.done():
                await title_task
                yield (
                    f"data: {json.dumps({'type': 'title', 'text': session.name})}\n\n"
                )
                title_task = None

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta.model_dump(exclude_none=True)

            reasoning = delta.get("reasoning_content")
            if reasoning:
                reasoning_parts.append(reasoning)
                yield (
                    f"data: {json.dumps({'type': 'reasoning', 'text': reasoning})}\n\n"
                )

            content = delta.get("content")
            if content:
                response_parts.append(content)
                yield (
                    f"data: {json.dumps({'type': 'answer', 'text': content})}\n\n"
                )

        # Save the answer before waiting for any unfinished title.
        session.messages.append(
            Message(
                persona="assistant",
                content="".join(response_parts),
                reasoning="".join(reasoning_parts),
                time=datetime.now(),
            )
        )

        # Handle a title that finishes after the answer.
        if title_task is not None:
            await title_task
            yield (
                f"data: {json.dumps({'type': 'title', 'text': session.name})}\n\n"
            )

    finally:
        if title_task is not None and not title_task.done():
            title_task.cancel()
            await asyncio.gather(title_task, return_exceptions=True)
 

@app.post("/session/{session_id}/chat")
async def chat(session_id: uuid.UUID, prompt: ChatRequest):
    target_session: Session = next(
        (session for session in session_store if session.id == session_id),
        None
    )
    if target_session is None:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    target_session.messages.append(
        Message(persona="user", content=prompt.message, time=datetime.now())
    )

    return StreamingResponse(llm_stream_chunk(target_session), media_type="text/event-stream")

@app.get("/session/{session_id}/chat")
async def get_chat(session_id: uuid.UUID) -> List[Message]:
    target_session: Session = next(
        (session for session in session_store if session.id == session_id),
        None
    )
    if target_session is None:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return target_session.messages

@app.post("/uploads")
async def upload_file(
    request: Request,
    filename: str = Query(min_length=1, max_length=255)
): 
    file_id = uuid.uuid4()

    temp_path = UPLOAD_DIR / f"{file_id}.part"
    suffix = Path(filename).suffix.lower()

    #---------------- Deprecated -----------------#
    #final_path= UPLOAD_DIR / f"{file_id}{suffix}"
    #---------------------------------------------#

    blob_name = f"{file_id}{suffix}"
    


    size = 0
    renamed = False
    registered = False

    try:
        async with aiofiles.open(temp_path, "wb") as destination:
            async for chunk in request.stream():
                if not chunk:
                    continue

                await destination.write(chunk)
                size += len(chunk)

        await run_in_threadpool(temp_path.replace, final_path)
        renamed = True

        metadata = {
            "id": file_id,
            "filename": filename,
            "size": size,
            "content-type": request.headers.get(
                "content-type", "application/octet-stream"
            ),
            "session_id": None,
            "status": "uploaded"
        }

        uploads[file_id] = metadata
        registered = True
        return metadata
    finally:
        if not registered:
            path_to_remove = final_path if renamed else temp_path
            await run_in_threadpool(
                path_to_remove.unlink,
                missing_ok=True
            )

@app.get("/uploads/{file_id}")
async def get_upload(file_id: uuid.UUID):
    upload = uploads.get(file_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="UPLOAD_NOT_FOUND")

    return upload

@app.post("/session/{session_id}/files")
async def attach_files(
    session_id: uuid.UUID,
    request: AttachFilesRequest
):
    session = next(
        (s for s in session_store if s.id == session_id),
        None,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    for file_id in request.file_ids:
        upload = uploads[file_id]
        if upload is None:
            raise HTTPException(status_code=404, detail="UPLOAD_NOT FOUND")

        if upload["session_id"] not in (None, session_id):
            raise HTTPException(status_code=409, detail="UPLOAD_ALREADY_ATTACHED")

    for file_id in request.file_ids:
        upload = uploads.get(file_id)
        upload["status"] = "processing"

        suffix = Path(upload["filename"]).suffix.lower()
        file_path = UPLOAD_DIR / f"{file_id}{suffix}"

        try:
            pages = await run_in_threadpool(extract_pages, file_path=file_path)
            chunks = await run_in_threadpool(chunk_pages, pages=pages)

            file_chunks[file_id] = [
                {
                    **chunk,
                    "file_id": file_id,
                    "session_id": session_id,
                    "filename": upload["filename"],
                }
                for chunk in chunks
            ]
            upload["session_id"] = session_id
            upload["status"] = "ready"
            upload["chunk_count"] = len(chunks)
        except Exception:
            upload["status"] = "failed"
            raise HTTPException(
                status_code=422,
                detail=f"Could not extract {upload['filename']}"
            )

    return {"attached": request.file_ids}






#Deprecated
# @app.post("/session/{session_id}/file")
# async def upload_file_stream(
#     session_id: uuid.UUID,
#     request: Request,
#     filename: str = Query(min_length=1)
# ):
#     target_session: Session = next(
#             (session for session in session_store if session.id == session_id),
#             None
#         )
#     if target_session is None:
#         raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

#     file_id = uuid.uuid4()
#     suffix = Path(filename).suffix.lower()
#     temporary_path = UPLOAD_DIR / f"{file_id}.part"
#     final_path = UPLOAD_DIR / f"{file_id}{suffix}"

#     size = 0
#     completed = False

#     try:
#         async with aiofiles.open(temporary_path, "wb") as destination:
#             async for chunk in request.stream():
#                 if chunk:
#                     await destination.write(chunk)
#                     size += len(chunk)
#         await run_in_threadpool(temporary_path.replace, final_path)

#         metadata = {
#             "id": str(file_id),
#             "filename": filename,
#             "size": size,
#             "content-type": request.headers.get(
#                 "content-type", "application/octet-stream"
#             )
#         }

#         session_files.setdefault(session_id, []).append(metadata)
#         completed = True
#         return metadata
#     finally:
#         if not completed:
#             await run_in_threadpool(temporary_path.unlink, missing_ok=True)

