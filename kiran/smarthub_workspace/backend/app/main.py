import json
import asyncio
import pika
import os
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import bcrypt
from jose import JWTError, jwt
from .database import SessionLocal, engine
from .models import Base, NotificationJob, User
import shutil
import uuid
from fastapi import FastAPI, Depends, HTTPException, status, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from .database import SessionLocal, engine, Base
from fastapi.responses import StreamingResponse
import httpx
from . import models, schemas
from .rag_client import rag_ingest_text, rag_upload_pdf, rag_ask_question
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartHub API", version="1.0")
# Create a directory to store profile pictures
os.makedirs("uploads/avatars", exist_ok=True)
# Tell FastAPI to serve files from this directory so the app can load them
app.mount("/static", StaticFiles(directory="uploads"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SECURITY CONFIGURATION ---
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_dev_key_change_in_prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # As per PDF spec

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: 
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None: 
        raise credentials_exception
    return user
# --- Pydantic Schemas ---

@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    phone: Optional[str] = Form(None),
    device_token: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None), # The optional image file
    db: Session = Depends(get_db)
    
):
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    avatar_url = None
    if avatar:
        # Generate a unique filename and save the file
        file_ext = avatar.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join("uploads/avatars", file_name)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
        
        avatar_url = f"/static/avatars/{file_name}"
    
    hashed_password = get_password_hash(password)
    initial_tokens = [device_token] if device_token else []
    
    new_user = models.User(
        email=email, 
        full_name=full_name, 
        hashed_password=hashed_password,
        phone=phone,
        avatar_url=avatar_url, # Save the path to the DB
        device_tokens=initial_tokens
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

# UPDATE YOUR PROFILE GETTER TO RETURN THE AVATAR
@app.get("/api/v1/auth/profile")
def get_profile(current_user: models.User = Depends(get_current_user)):
    return {
        "email": current_user.email, 
        "full_name": current_user.full_name, 
        "phone": current_user.phone,
        "avatar_url": current_user.avatar_url
    }
# Add this endpoint under your /auth/login route
@app.post("/api/v1/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/auth/forgot-password")
def forgot_password(request: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    if not user:
        # Security best practice: Don't reveal if an email exists
        return {"message": "If that email is registered, a reset link has been sent."}
    
    # 1. Generate a secure reset token (valid for 15 minutes)
    reset_token = create_access_token(
        data={"sub": user.email, "type": "password_reset"}, 
        expires_delta=timedelta(minutes=15)
    )
    
    # 2. Construct the frontend reset link (assuming frontend runs on port 3000)
    reset_link = f"http://localhost:8000/reset-password?token={reset_token}"
    
    # 3. Create the RabbitMQ payload
    email_payload = [{
        "job_id": str(uuid.uuid4()), # Generate a random job ID for this single task
        "task_id": 1,
        "recipient": user.email,
        "message": f"Please click the following link to reset your SmartHub password: {reset_link}",
        "simulate_failure": False 
    }]
    
    # 4. Push to the worker queue
    publish_batch_to_queue("email.process", email_payload)
    
    return {"message": "If that email is registered, a reset link has been sent."}


@app.post("/api/v1/auth/reset-password")
def reset_password(request: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired reset token",
    )
    
    try:
        # 1. Decode and verify the token
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        # Ensure this is specifically a reset token, not a standard login token
        if email is None or token_type != "password_reset":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
        
    # 2. Find the user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise credentials_exception
        
    # 3. Hash the new password and save it
    user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password has been reset successfully. You can now log in."}

# --- SECURITY DEPENDENCY ---
# This function intercepts requests, reads the token, and fetches the secure user.
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

# --- PROFILE ENDPOINTS ---

@app.put("/api/v1/auth/profile")
def update_profile(profile: schemas.ProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.full_name = profile.full_name
    current_user.phone = profile.phone
    db.commit()
    return {"message": "Profile updated successfully"}
# ==========================================
# --- MODULE: ADMIN ---
# ==========================================

@app.get("/api/v1/admin/users")
def list_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """List all users"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return db.query(models.User).order_by(models.User.created_at.desc()).all()

@app.delete("/api/v1/admin/users/{id}")
def delete_user(id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Delete a user account"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    user_to_delete = db.query(models.User).filter(models.User.id == id).first()
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(user_to_delete)
    db.commit()
    return {"message": "User deleted successfully"}
@app.post("/api/v1/auth/logout")
def logout():
    # Since JWTs are stateless, actual logout is handled by the Flutter app deleting the token.
    # This endpoint satisfies the PDF specification for the backend API.
    return {"message": "Successfully logged out"}
# --- QUEUE ENDPOINTS (From Previous Step) ---
# ... Keep your existing /notify/bulk and /notify/jobs/{job_id} endpoints here ...

# RabbitMQ Publisher Setup
def publish_batch_to_queue(queue_name: str, messages: list):
    """Opens ONE connection, sends ALL messages, then closes."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    
    # Ensure the queue exists before publishing
    channel.queue_declare(queue=queue_name, durable=True)
    
    for message in messages:
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
            )
        )
        
    # Close the connection only after all messages are sent
    connection.close()
# --- ADD TO NOTIFICATIONS SECTION ---

@app.get("/api/v1/notify/jobs")
def list_all_jobs(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """List all bulk notification jobs (Admin only)"""
    # Assuming only admins can view all bulk queues
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return db.query(models.NotificationJob).order_by(models.NotificationJob.created_at.desc()).all()

@app.post("/api/v1/notify/send")
def send_single_notification(
    # Assuming you have a schemas.SingleNotificationRequest
    payload: dict, # Replace with proper schema if created
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Send a single immediate notification"""
    # Simply push a single task to the RabbitMQ queue immediately
    queue_target = f"{payload.get('channel', 'email')}.process"
    task = [{
        "job_id": "single_send",
        "task_id": str(uuid.uuid4()),
        "recipient": payload.get('recipient'),
        "message": payload.get('message')
    }]
    publish_batch_to_queue(queue_target, task)
    return {"message": "Notification dispatched"}

@app.post("/api/v1/notify/bulk", status_code=202)
def create_bulk_job(job: schemas.BulkJobRequest, db: Session = Depends(get_db)):
    # 1. Create the job record in PostgreSQL
    new_job = NotificationJob(
        channel=job.channel,
        total=job.total,
        sent=0,
        failed=0,
        retrying=0
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # 2. Determine the target queue based on the channel
    queue_target = f"{job.channel}.process" # e.g., email.process or sms.process

    # 3. Compile all tasks into a single list
    # 3. Compile all tasks into a single list
    tasks = []
    for i in range(job.total):
        tasks.append({
            "job_id": str(new_job.id),
            "task_id": i + 1,
            "recipient": f"user_{i}@example.com",
            
        })
        
    # 4. Fire the entire batch through a single RabbitMQ connection
    publish_batch_to_queue(queue_target, tasks)

    return {"job_id": new_job.id, "status": "queued"}

@app.get("/api/v1/notify/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(NotificationJob).filter(NotificationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "channel": job.channel,
        "total": job.total,
        "sent": job.sent,
        "failed": job.failed,
        "retrying": job.retrying,
        "completed": job.completed
    }
# ==========================================
# --- MODULE 3: DOCUMENTS ENDPOINTS ---
# ==========================================

# Create a local storage directory for uploaded documents
os.makedirs("uploads/documents", exist_ok=True)

@app.post("/api/v1/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Accepts PDF, DOCX, TXT, PNG/JPG files and saves them to local storage.
    PDF and TXT files are automatically forwarded to the RAG engine for vector indexing."""
    
    # 1. Determine file type
    ext = file.filename.split(".")[-1].lower()
    allowed_types = {"pdf": "pdf", "docx": "docx", "txt": "txt", "png": "image", "jpg": "image", "jpeg": "image"}
    
    if ext not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file format")
        
    file_type = allowed_types[ext]
    
    # 2. Save physical file
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join("uploads/documents", safe_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(file_path)
    
    # 3. Save to database
    new_doc = models.Document(
        user_id=current_user.id,
        session_id=session_id,
        filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        storage_path=file_path,
        processed=False
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # 4. Forward to RAG engine for vector indexing (PDF and TXT only)
    if file_type in ("pdf", "txt"):
        try:
            if file_type == "pdf":
                file.file.seek(0)  # Reset file pointer after saving
                rag_result = await rag_upload_pdf(file, session_id=session_id)
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()
                rag_result = await rag_ingest_text(text_content, source=file.filename, session_id=session_id)
            
            new_doc.processed = True
            new_doc.chunk_count = rag_result.get("chunks", 0)
            db.commit()
            print(f"[RAG] Indexed '{file.filename}': {rag_result.get('chunks', 0)} chunks")
        except Exception as e:
            print(f"[RAG] Indexing failed for '{file.filename}': {e}")
            # File is saved to disk and DB, just not vector-indexed yet
    
    return {
        "message": "Document uploaded successfully",
        "document_id": str(new_doc.id),
        "processed": new_doc.processed,
        "chunk_count": new_doc.chunk_count
    }

@app.get("/api/v1/documents")
def list_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all documents belonging to the current user."""
    documents = db.query(models.Document).filter(models.Document.user_id == current_user.id).all()
    return documents

@app.delete("/api/v1/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Deletes the file from disk and removes DB record."""
    doc = db.query(models.Document).filter(models.Document.id == document_id, models.Document.user_id == current_user.id).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # 1. Delete physical file
    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
        
    # 2. Delete from DB
    db.delete(doc)
    db.commit()
    
    return {"message": "Document deleted successfully"}

from typing import Optional
# (Ensure schemas.TodoCreate and schemas.TodoUpdate are in your schemas.py)

# ==========================================
# --- MODULE 6: TODOS ENDPOINTS ---
# ==========================================

@app.get("/api/v1/todos")
def list_todos(
    completed: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Fetch all active todos for the current user."""
    query = db.query(models.Todo).filter(models.Todo.user_id == current_user.id)
    if completed is not None:
        query = query.filter(models.Todo.completed == completed)
    return query.all()

@app.post("/api/v1/todos", status_code=status.HTTP_201_CREATED)
def create_todo(
    todo: schemas.TodoCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Add a new task."""
    new_todo = models.Todo(
        user_id=current_user.id,
        title=todo.title,
        description=todo.description,
        due_date=todo.due_date
    )
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo

@app.put("/api/v1/todos/{todo_id}")
def update_todo(
    todo_id: str,
    todo_update: schemas.TodoUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Edit an existing task title or due date."""
    todo = db.query(models.Todo).filter(models.Todo.id == todo_id, models.Todo.user_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
        
    if todo_update.title:
        todo.title = todo_update.title
    if todo_update.due_date:
        todo.due_date = todo_update.due_date
        
    db.commit()
    db.refresh(todo)
    return todo

@app.put("/api/v1/todos/{todo_id}/complete")
def toggle_todo_complete(
    todo_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Toggle a task between finished and unfinished."""
    todo = db.query(models.Todo).filter(models.Todo.id == todo_id, models.Todo.user_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
        
    todo.completed = not todo.completed
    db.commit()
    return {"message": "Status updated", "completed": todo.completed}

@app.delete("/api/v1/todos/{todo_id}")
def delete_todo(
    todo_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Permanently delete a task."""
    todo = db.query(models.Todo).filter(models.Todo.id == todo_id, models.Todo.user_id == current_user.id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
        
    db.delete(todo)
    db.commit()
    return {"message": "Todo deleted"}
# ==========================================
# --- MODULE 2: AI CHAT SESSIONS ---
# ==========================================

@app.post("/api/v1/chat/sessions", status_code=status.HTTP_201_CREATED)
def create_chat_session(
    session: schemas.ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create new chat session"""
    new_session = models.ChatSession(user_id=current_user.id, title=session.title)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@app.get("/api/v1/chat/sessions")
def list_user_sessions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List user's sessions"""
    return db.query(models.ChatSession).filter(
        models.ChatSession.user_id == current_user.id
    ).order_by(models.ChatSession.created_at.desc()).all()

@app.get("/api/v1/chat/sessions/{id}/messages")
def get_session_history(
    id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get message history"""
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == id, models.ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == id
    ).order_by(models.ChatMessage.created_at.asc()).all()

@app.delete("/api/v1/chat/sessions/{id}")
def delete_chat_session(
    id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete session + messages"""
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == id, models.ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.delete(session)
    db.commit()
    return {"message": "Chat session deleted"}

@app.post("/api/v1/chat/sessions/{id}/messages")
async def send_message_to_ai(
    id: str,
    message: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Send message with RAG-grounded answers via SSE stream.
    
    Flow:
    1. Try the RAG engine first for document-grounded answers
    2. If RAG has relevant sources, stream the grounded answer
    3. If RAG has no context or is unavailable, fall back to direct Ollama streaming
    """
    # 1. Verify Session
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == id, models.ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. Save User Message
    user_msg = models.ChatMessage(session_id=id, role="user", content=message.content)
    db.add(user_msg)
    db.commit()

    # 3. Pull short history for Ollama fallback
    history = db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == id
    ).order_by(models.ChatMessage.created_at.asc()).limit(10).all()

    # 4. SSE Generator function
    async def streaming_generator():
        full_ai_response = ""
        used_rag = False

        # --- Step A: Try RAG engine for grounded answer ---
        try:
            yield f"data: {json.dumps({'type': 'log', 'message': 'Searching your documents...'})}\n\n"
            rag_result = await rag_ask_question(message.content, session_id=id)
            rag_answer = rag_result.get("answer", "")
            rag_sources = rag_result.get("sources", [])

            # Only use RAG if it found relevant sources
            if rag_answer and rag_sources:
                used_rag = True
                yield f"data: {json.dumps({'type': 'log', 'message': f'Found {len(rag_sources)} relevant sources'})}\n\n"

                # Stream the RAG answer preserving all newline and markdown formatting
                full_ai_response = rag_answer
                lines = full_ai_response.split("\n")
                for line_idx, line in enumerate(lines):
                    words = line.split(" ")
                    for i in range(0, len(words), 3):
                        chunk = " ".join(words[i:i+3])
                        # Add trailing space unless it's the last chunk of the line
                        if i + 3 < len(words):
                            chunk += " "
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                        await asyncio.sleep(0.02)
                    
                    # Yield a newline back if there are more lines
                    if line_idx < len(lines) - 1:
                        yield f"data: {json.dumps({'type': 'content', 'content': '\n'})}\n\n"

                # Send source citations to the client
                yield f"data: {json.dumps({'type': 'sources', 'sources': rag_sources})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            print(f"[RAG] Query failed, falling back to direct Ollama: {e}")

        # --- Step B: Fallback to direct Ollama streaming ---
        if not used_rag:
            yield f"data: {json.dumps({'type': 'log', 'message': 'Using general knowledge...'})}\n\n"

            sys_prompt = "You are SmartHub, an AI assistant for TKM students."
            ollama_payload = [{"role": "system", "content": sys_prompt}]
            for past in history:
                ollama_payload.append({"role": past.role, "content": past.content})

            async with httpx.AsyncClient() as client:
                try:
                    async with client.stream(
                        "POST", "http://localhost:11434/api/chat",
                        json={"model": "qwen3.5:4b", "messages": ollama_payload, "stream": True},
                        timeout=60.0
                    ) as response:
                        async for raw_line in response.aiter_lines():
                            if raw_line:
                                chunk_data = json.loads(raw_line)
                                if "message" in chunk_data and "content" in chunk_data["message"]:
                                    delta = chunk_data["message"]["content"]
                                    full_ai_response += delta
                                    yield f"data: {json.dumps({'type': 'content', 'content': delta})}\n\n"
                                if chunk_data.get("done"):
                                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                                    break
                except httpx.ConnectError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI service connection failed. Make sure Ollama is running.'})}\n\n"
                    return

        # --- Step C: Save AI response to chat history ---
        if full_ai_response:
            db_write = SessionLocal()
            try:
                ai_msg = models.ChatMessage(session_id=id, role="assistant", content=full_ai_response)
                db_write.add(ai_msg)
                db_write.commit()
            finally:
                db_write.close()

    return StreamingResponse(streaming_generator(), media_type="text/event-stream")