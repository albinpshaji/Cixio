from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    phone: Optional[str] = None
    device_token: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
class ProfileUpdate(BaseModel):
    full_name: str
    phone: Optional[str] = None

class BulkJobRequest(BaseModel):
    channel: str
    total: int

# Stubs for upcoming modules
# --- MODULE 6: TODOS ---
class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None

# --- MODULE 2: CHAT SESSIONS ---
class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"

class ChatMessageCreate(BaseModel):
    content: str