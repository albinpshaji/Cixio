from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str | None = None


class SessionUpdate(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime


class IngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str | None = None
    sessionId: str | None = None


class IngestResponse(BaseModel):
    source: str
    chunks: int


class UploadResponse(BaseModel):
    source: str
    chunks: int
    pages: int


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    sessionId: str | None = None
    think: bool = True
    think_level: str = "medium"
    search_depth: str = "balanced"
    hyde: bool = False
    priority_docs: list[str] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    id: int
    content: str
    metadata: dict[str, Any] | None
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunk]


class ErrorResponse(BaseModel):
    error: str


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    sources: list[RetrievedChunk]
    thoughts: str | None = None
    token_usage: dict[str, int] | None = None
    created_at: datetime


class DocumentItem(BaseModel):
    filename: str
    chunk_count: int
    uploaded_at: str | None = None
    session_id: str | None = None


class UserRegister(BaseModel):
    email: str
    full_name: str
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
