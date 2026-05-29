import json
import httpx
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from psycopg.types.json import Jsonb

from app.chunking import chunk_text
from app.config import settings
from app.db import close_pool, open_pool, pool
from app.ollama import create_embedding, generate_answer
from app.pdf import extract_pdf_chunks
from app.prompts import build_rag_prompt
from app.retrieval import retrieve_relevant_chunks
from app.schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
    UploadResponse,
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    MessageResponse,
    RetrievedChunk,
    DocumentItem,
)
from app.vector import to_pg_vector


@dataclass(frozen=True)
class ChunkToStore:
    content: str
    metadata: dict[str, Any]


def init_db():
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    title VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    thoughts TEXT,
                    token_usage JSONB,
                    sources JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                """
            )
            cursor.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS thoughts TEXT")
            cursor.execute("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS token_usage JSONB")
            connection.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    try:
        init_db()
        yield
    finally:
        close_pool()


app = FastAPI(
    title="Local RAG Engine API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def clean_source(source: str | None, fallback: str = "pasted text") -> str:
    value = source.strip() if source else ""
    return value or fallback


def store_chunks(chunks: list[ChunkToStore]) -> None:
    ingested_at = datetime.now(timezone.utc).isoformat()
    embedded_chunks: list[tuple[str, Jsonb, str]] = []

    for chunk in chunks:
        embedding = create_embedding(chunk.content)
        embedded_chunks.append(
            (
                chunk.content,
                Jsonb({**chunk.metadata, "ingestedAt": ingested_at}),
                to_pg_vector(embedding),
            )
        )

    with pool.connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO documents (content, metadata, embedding)
                    VALUES (%s, %s::jsonb, %s::vector)
                    """,
                    embedded_chunks,
                )


@app.post("/api/ingest", response_model=IngestResponse)
def ingest_document(request: IngestRequest) -> IngestResponse:
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Document text is required.")

    chunks = chunk_text(text)

    if not chunks:
        raise HTTPException(status_code=400, detail="No usable text chunks were found.")

    source = clean_source(request.source)
    chunks_to_store = [
        ChunkToStore(
            content=chunk.content,
            metadata={
                "source": source,
                "chunkIndex": chunk.chunk_index,
                "sessionId": request.sessionId,
            },
        )
        for chunk in chunks
    ]

    try:
        store_chunks(chunks_to_store)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return IngestResponse(source=source, chunks=len(chunks))


@app.post("/api/upload", response_model=UploadResponse)
def upload_pdf(
    file: UploadFile = File(...),
    sessionId: str | None = Form(None)
) -> UploadResponse:
    source, pages, pdf_chunks = extract_pdf_chunks(file)
    chunks_to_store = [
        ChunkToStore(
            content=chunk.content,
            metadata={
                "source": chunk.source,
                "page": chunk.page,
                "chunkIndex": chunk.chunk_index,
                "pageChunkIndex": chunk.page_chunk_index,
                "sessionId": sessionId,
            },
        )
        for chunk in pdf_chunks
    ]

    try:
        store_chunks(chunks_to_store)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return UploadResponse(source=source, chunks=len(pdf_chunks), pages=pages)


@app.post("/api/chat")
async def chat(request: ChatRequest, raw_request: Request):
    question = request.question.strip()
    sessionId = request.sessionId

    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    # 1. Store user message in history if session is active
    if sessionId:
        try:
            with pool.connection() as connection:
                with connection.cursor() as cursor:
                    # Check if session exists, otherwise create it
                    cursor.execute("SELECT id FROM chat_sessions WHERE id = %s", (sessionId,))
                    if not cursor.fetchone():
                        cursor.execute(
                            "INSERT INTO chat_sessions (id, title) VALUES (%s, %s)",
                            (sessionId, question[:50] or "Chat Session"),
                        )
                    # Save user query
                    cursor.execute(
                        "INSERT INTO chat_messages (session_id, role, content, sources) VALUES (%s, %s, %s, %s)",
                        (sessionId, "user", question, Jsonb([])),
                    )
                    connection.commit()
        except Exception as db_err:
            print(f"[DB Error] Failed to save user query: {db_err}")

    # 2. Retrieve grounded sources
    try:
        if request.search_depth == "fast":
            limit = 4
        elif request.search_depth == "deep":
            limit = 12
        else:
            limit = 8
        sources = retrieve_relevant_chunks(question, sessionId=sessionId, limit=limit)
    except Exception as retrieve_err:
        print(f"[Retrieve Error] Failed: {retrieve_err}")
        sources = []

    # 3. Define SSE Generator
    async def sse_generator():
        # Yield matching sources first
        sources_data = [
            {
                "id": s.id,
                "content": s.content,
                "metadata": s.metadata,
                "similarity": s.similarity
            }
            for s in sources
        ]
        usage_stats = {"prompt_tokens": 0, "eval_tokens": 0}
        yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        if not sources:
            default_answer = "I could not find any document chunks to search. Ingest a document first."
            yield f"event: token\ndata: {json.dumps(default_answer)}\n\n"
            # Save assistant response to DB
            if sessionId:
                try:
                    with pool.connection() as connection:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "INSERT INTO chat_messages (session_id, role, content, sources) VALUES (%s, %s, %s, %s)",
                                (sessionId, "assistant", default_answer, Jsonb([])),
                            )
                            connection.commit()
                except Exception as db_err:
                    print(db_err)
            return

        prompt = build_rag_prompt(question, sources, think_level=request.think_level)
        full_response = ""
        full_thinking = ""
        
        should_think = request.think and request.think_level in ["medium", "max"]
        
        try:
            timeout = httpx.Timeout(settings.generation_timeout_ms / 1000)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": settings.ollama_chat_model,
                        "prompt": prompt,
                        "stream": True,
                        "think": should_think,
                        "options": {
                            "num_predict": settings.generation_max_tokens,
                            "temperature": 0.2,
                            "think": should_think,
                            "num_ctx": settings.ollama_num_ctx,
                        },
                    }
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if await raw_request.is_disconnected():
                            print("[Abort] Client connection closed. Stopping background generation.")
                            break
                        if not line:
                            continue
                        parsed = json.loads(line)
                        token = parsed.get("response", "")
                        thinking = parsed.get("thinking", "")
                        
                        if thinking:
                            full_thinking += thinking
                            yield f"event: thinking\ndata: {json.dumps(thinking)}\n\n"
                        elif token:
                            full_response += token
                            yield f"event: token\ndata: {json.dumps(token)}\n\n"

                        if parsed.get("done", False):
                            usage_stats["prompt_tokens"] = parsed.get("prompt_eval_count", 0)
                            usage_stats["eval_tokens"] = parsed.get("eval_count", 0)
                            if usage_stats["prompt_tokens"] or usage_stats["eval_tokens"]:
                                yield f"event: usage\ndata: {json.dumps(usage_stats)}\n\n"
        except Exception as error:
            error_msg = f"\n[Generation Error: {error}]"
            yield f"event: token\ndata: {json.dumps(error_msg)}\n\n"
            full_response += error_msg

        # 4. Save final assistant response to history
        if sessionId and (full_response or full_thinking):
            try:
                db_usage = usage_stats if (usage_stats["prompt_tokens"] or usage_stats["eval_tokens"]) else None
                with pool.connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO chat_messages (session_id, role, content, thoughts, token_usage, sources) VALUES (%s, %s, %s, %s, %s, %s)",
                            (sessionId, "assistant", full_response, full_thinking or None, Jsonb(db_usage) if db_usage else None, Jsonb(sources_data)),
                        )
                        connection.commit()
            except Exception as db_err:
                print(f"[DB Error] Failed to save assistant query: {db_err}")

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions():
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, title, created_at FROM chat_sessions ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [SessionResponse(id=str(row[0]), title=row[1], created_at=row[2]) for row in rows]


@app.post("/api/sessions", response_model=SessionResponse, status_code=201)
def create_session(request: SessionCreate):
    title = request.title.strip() if request.title else "New Chat"
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_sessions (title) VALUES (%s) RETURNING id, title, created_at",
                (title,),
            )
            row = cursor.fetchone()
            connection.commit()
            return SessionResponse(id=str(row[0]), title=row[1], created_at=row[2])


@app.put("/api/sessions/{session_id}", response_model=SessionResponse)
def update_session(session_id: str, request: SessionUpdate):
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE chat_sessions SET title = %s WHERE id = %s RETURNING id, title, created_at",
                (title, session_id),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            connection.commit()
            return SessionResponse(id=str(row[0]), title=row[1], created_at=row[2])


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
            connection.commit()
    return {"status": "success", "message": "Session deleted"}


@app.get("/api/sessions/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(session_id: str):
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, session_id, role, content, thoughts, token_usage, sources, created_at FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,),
            )
            rows = cursor.fetchall()
            return [
                MessageResponse(
                    id=str(row[0]),
                    session_id=str(row[1]),
                    role=row[2],
                    content=row[3],
                    thoughts=row[4],
                    token_usage=row[5],
                    sources=[
                        RetrievedChunk(
                            id=s.get("id", 0),
                            content=s.get("content", ""),
                            metadata=s.get("metadata", {}),
                            similarity=s.get("similarity", 0.0),
                        )
                        for s in (row[6] or [])
                    ],
                    created_at=row[7],
                )
                for row in rows
            ]


@app.get("/api/documents", response_model=list[DocumentItem])
def list_documents():
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    metadata->>'source' AS filename,
                    count(*) AS chunk_count,
                    max(metadata->>'ingestedAt') AS uploaded_at,
                    metadata->>'sessionId' AS session_id
                FROM documents
                GROUP BY metadata->>'source', metadata->>'sessionId'
                ORDER BY uploaded_at DESC
                """
            )
            rows = cursor.fetchall()
            return [
                DocumentItem(
                    filename=row[0] or "pasted text",
                    chunk_count=row[1],
                    uploaded_at=row[2],
                    session_id=row[3],
                )
                for row in rows
            ]


@app.delete("/api/documents")
def delete_document(filename: str, sessionId: str | None = None):
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            if sessionId and sessionId != "null" and sessionId != "undefined":
                cursor.execute(
                    "DELETE FROM documents WHERE metadata->>'source' = %s AND metadata->>'sessionId' = %s",
                    (filename, sessionId),
                )
            else:
                cursor.execute(
                    "DELETE FROM documents WHERE metadata->>'source' = %s AND (metadata->>'sessionId' IS NULL OR metadata->>'sessionId' = 'null')",
                    (filename,),
                )
            connection.commit()
    return {"status": "success", "message": f"Document {filename} deleted successfully."}
