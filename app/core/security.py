import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet
from fastapi import Request, Depends, HTTPException, status, WebSocket
from app.core.database import engine
from app.core.config import get_settings
from sqlmodel import Session, select
from jose import jwt, JWTError

settings = get_settings()
logger = logging.getLogger(__name__)

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"


# --- Encryption Utilities ---

def get_fernet() -> Fernet:
    """Derives a Fernet key from the SECRET_KEY and returns a Fernet instance.

    Why: Fernet requires a 32-byte url-safe base64-encoded key. We derive this
    from the application's SECRET_KEY to ensure consistency and security.
    """
    key_bytes = settings.SECRET_KEY.encode()
    hash_object = hashlib.sha256(key_bytes)
    key_32 = base64.urlsafe_b64encode(hash_object.digest())
    return Fernet(key_32)


def encrypt_secret(plain_text: str) -> str:
    """Encrypts a string using Fernet symmetric encryption.

    Args:
        plain_text: The sensitive data to encrypt.

    Returns:
        The encrypted token as a string.
    """
    if not plain_text:
        return ""
    f = get_fernet()
    return f.encrypt(plain_text.encode()).decode()


def decrypt_secret(cipher_text: str) -> str:
    """Decrypts a Fernet token back to its original string.

    Args:
        cipher_text: The encrypted token.

    Returns:
        The original plain-text string.
    """
    if not cipher_text:
        return ""
    try:
        f = get_fernet()
        return f.decrypt(cipher_text.encode()).decode()
    except Exception:
        return cipher_text


# --- Authentication Utilities ---

async def get_current_user(request: Request) -> str:
    """Dependency that checks if the user is authenticated via JWT cookie.
    Returns username if valid, raises 401 otherwise.
    """
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    user_data = get_user_from_token(token)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_data["username"]


def get_user_from_token(token: str) -> Optional[dict]:
    """Decodes a JWT token and extracts user info."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "watcher")
        if username is None:
            return None
        return {"username": username, "role": role}
    except JWTError:
        return None


def check_auth(request: Request) -> bool:
    """Synchronous helper for middleware to verify JWT cookie."""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return False

        if token.startswith("Bearer "):
            token = token[7:]

        return get_user_from_token(token) is not None
    except Exception as e:
        logger.error(f"Auth Check Error: {e}")
        return False


async def get_current_user_ws(websocket: WebSocket) -> Optional[str]:
    """WebSocket dependency to check auth via Cookie."""
    token = websocket.cookies.get("access_token")
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        return None

    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None


from app.models import UserRole


class RoleChecker:
    """FastAPI dependency that enforces role-based access control."""

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, user: str = Depends(get_current_user)):
        with Session(engine) as session:
            from app.models import User
            statement = select(User).where(User.username == user)
            db_user = session.exec(statement).first()
            if not db_user:
                raise HTTPException(status_code=401, detail="User not found")

            # Check if user's role string value is in allowed roles
            user_role_val = db_user.role.value if hasattr(db_user.role, 'value') else str(db_user.role)
            
            if user_role_val not in self.allowed_roles:
                if user_role_val == "admin": # Admin always has access
                    return db_user
                raise HTTPException(status_code=403, detail="Operation not permitted")
            return db_user
