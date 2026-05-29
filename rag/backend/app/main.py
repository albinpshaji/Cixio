from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from psycopg.types.json import Jsonb

from app.chunking import chunk_text
from app.config import settings
from app.db import close_pool, open_pool, pool
from app.ollama import create_embedding, generate_answer
from app.pdf import extract_pdf_chunks
from app.prompts import build_rag_prompt
from app.retrieval import retrieve_relevant_chunks
from app.schemas import ChatRequest, ChatResponse, IngestRequest, IngestResponse, UploadResponse
from app.vector import to_pg_vector


@dataclass(frozen=True)
class ChunkToStore:
    content: str
    metadata: dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    try:
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
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):[0-9]+",
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


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    try:
        sources = retrieve_relevant_chunks(question, sessionId=request.sessionId)

        if not sources:
            return ChatResponse(
                answer="I could not find any document chunks to search. Ingest a document first.",
                sources=[],
            )

        prompt = build_rag_prompt(question, sources)
        answer = generate_answer(prompt)

        return ChatResponse(answer=answer, sources=sources)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
