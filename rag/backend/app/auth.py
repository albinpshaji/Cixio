import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.db import pool
from app.schemas import (
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


# ── Password Utilities ──────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── Token Utilities ──────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_expiry_minutes
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expiry_days
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str, expected_type: str = "access") -> str:
    """Decode JWT and return the user_id (sub). Raises HTTPException on failure."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if user_id is None or token_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired or is invalid",
        )


# ── FastAPI Dependency: Current User ────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Extract and validate the current user from the Authorization header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_token(credentials.credentials, expected_type="access")

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, email, full_name, avatar_url, is_active, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not row[4]:  # is_active
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return {
        "id": str(row[0]),
        "email": row[1],
        "full_name": row[2],
        "avatar_url": row[3],
        "created_at": row[5],
    }


# ── Database Init ────────────────────────────────────────────────

def init_auth_tables() -> None:
    """Create users and refresh_tokens tables if they don't exist."""
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    avatar_url TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            connection.commit()


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(request: UserRegister):
    """Create a new user account and return JWT tokens."""
    email = request.email.strip().lower()
    full_name = request.full_name.strip()

    if not email or not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and full name are required",
        )

    hashed = hash_password(request.password)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists",
                )

            # Create user
            cursor.execute(
                """
                INSERT INTO users (email, full_name, hashed_password)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (email, full_name, hashed),
            )
            user_id = str(cursor.fetchone()[0])

            # Generate tokens
            access_token = create_access_token(user_id)
            refresh_token = create_refresh_token(user_id)

            # Store refresh token hash
            cursor.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    hash_token(refresh_token),
                    datetime.now(timezone.utc)
                    + timedelta(days=settings.jwt_refresh_expiry_days),
                ),
            )
            connection.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: UserLogin):
    """Authenticate user and return JWT tokens."""
    email = request.email.strip().lower()

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, hashed_password, is_active FROM users WHERE email = %s",
                (email,),
            )
            row = cursor.fetchone()

            if row is None or not verify_password(request.password, row[1]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )

            if not row[2]:  # is_active
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is deactivated",
                )

            user_id = str(row[0])

            # Generate tokens
            access_token = create_access_token(user_id)
            refresh_token = create_refresh_token(user_id)

            # Store refresh token hash
            cursor.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    hash_token(refresh_token),
                    datetime.now(timezone.utc)
                    + timedelta(days=settings.jwt_refresh_expiry_days),
                ),
            )
            connection.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(request: RefreshRequest):
    """Use a valid refresh token to get a new access + refresh token pair."""
    # Decode the refresh token
    user_id = decode_token(request.refresh_token, expected_type="refresh")
    token_digest = hash_token(request.refresh_token)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            # Check if refresh token is valid and not revoked
            cursor.execute(
                """
                SELECT id, revoked, expires_at FROM refresh_tokens
                WHERE user_id = %s AND token_hash = %s
                """,
                (user_id, token_digest),
            )
            row = cursor.fetchone()

            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )

            if row[1]:  # revoked
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been revoked",
                )

            if row[2] < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has expired",
                )

            # Revoke old refresh token (rotation)
            cursor.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE id = %s",
                (row[0],),
            )

            # Issue new token pair
            new_access = create_access_token(user_id)
            new_refresh = create_refresh_token(user_id)

            cursor.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    hash_token(new_refresh),
                    datetime.now(timezone.utc)
                    + timedelta(days=settings.jwt_refresh_expiry_days),
                ),
            )
            connection.commit()

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        avatar_url=current_user["avatar_url"],
        created_at=current_user["created_at"],
    )


@router.post("/logout")
def logout(
    request: RefreshRequest,
    current_user: dict = Depends(get_current_user),
):
    """Revoke the given refresh token (logout)."""
    token_digest = hash_token(request.refresh_token)

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE refresh_tokens SET revoked = TRUE
                WHERE user_id = %s AND token_hash = %s AND revoked = FALSE
                """,
                (current_user["id"], token_digest),
            )
            connection.commit()

    return {"status": "success", "message": "Logged out successfully"}
