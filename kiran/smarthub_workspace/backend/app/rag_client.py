"""
RAG Engine Client — Thin HTTP wrapper around the standalone RAG engine API.

The RAG engine runs as a separate service (default: http://localhost:8001)
and handles all embedding, chunking, vector storage, retrieval, and LLM generation.

SmartHub calls these functions to offload AI work to the RAG engine.
"""

import os
import httpx
from fastapi import UploadFile

RAG_BASE_URL = os.getenv("RAG_API_BASE_URL", "http://localhost:8001")
RAG_TIMEOUT = 120.0  # Embedding + LLM generation can be slow on local hardware


async def rag_health_check() -> dict:
    """Check if the RAG engine is reachable."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{RAG_BASE_URL}/health")
        response.raise_for_status()
        return response.json()


async def rag_ingest_text(text: str, source: str = "pasted text", session_id: str | None = None) -> dict:
    """
    Send plain text to the RAG engine for chunking, embedding, and storage.

    Calls: POST /api/ingest
    Returns: {"source": "...", "chunks": 12}
    """
    payload = {"text": text, "source": source}
    if session_id:
        payload["sessionId"] = str(session_id)

    async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
        response = await client.post(
            f"{RAG_BASE_URL}/api/ingest",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def rag_upload_pdf(file: UploadFile, session_id: str | None = None) -> dict:
    """
    Forward a PDF file to the RAG engine for extraction, chunking, and embedding.

    Calls: POST /api/upload
    Returns: {"source": "...", "chunks": 8, "pages": 3}
    """
    file.file.seek(0)
    data = {}
    if session_id:
        data["sessionId"] = str(session_id)

    async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
        response = await client.post(
            f"{RAG_BASE_URL}/api/upload",
            files={"file": (file.filename, file.file, file.content_type or "application/pdf")},
            data=data,
        )
        response.raise_for_status()
        return response.json()


async def rag_ask_question(question: str, session_id: str | None = None) -> dict:
    """
    Ask the RAG engine a question grounded in previously ingested documents.

    Calls: POST /api/chat
    Returns: {"answer": "...", "sources": [{"id": ..., "content": ..., "similarity": ...}, ...]}
    """
    payload = {"question": question}
    if session_id:
        payload["sessionId"] = str(session_id)

    async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
        response = await client.post(
            f"{RAG_BASE_URL}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
