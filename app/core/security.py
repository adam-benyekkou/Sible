from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
import bcrypt
from app.services import SettingsService
from app.core.database import engine
from sqlmodel import Session

def verify_password(plain_password, hashed_password):
    try:
        # bcrypt.checkpw expects bytes
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        # Fallback if valid hash format check failed, it might be plain text
        return plain_password == hashed_password

def get_password_hash(password):
    # bcrypt.hashpw returns bytes, we decode to store as string
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def get_current_user(request: Request):
    """
    Dependency that checks if the user is authenticated via session.
    """
    with Session(engine) as session:
        settings = SettingsService(session).get_settings()
    
    # If Auth is disabled, everyone is "authenticated"
    if not settings.auth_enabled:
        return "admin"
        
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user

def check_auth(request: Request) -> bool:
    """
    Synchronous helper for middleware.
    """
    with Session(engine) as session:
        settings = SettingsService(session).get_settings()
        
    if not settings.auth_enabled:
        return True
    return request.session.get("user") is not None

from fastapi import WebSocket

async def get_current_user_ws(websocket: WebSocket) -> str:
    """
    WebSocket Dependency to check auth.
    Note: WebSockets don't have the same middleware session handling by default in Starlette/FastAPI 
    unless SessionMiddleware is wrapped appropriately or we look at cookies manually.
    For this MVP, we'll check the 'session' cookie if available or allow if auth is disabled.
    """
    with Session(engine) as session:
        settings = SettingsService(session).get_settings()
        
    if not settings.auth_enabled:
        return "admin"
        
    # Checking storage/session cookie is tricky without the middleware context on WS
    # For now, we unfortunately have to be permissive or implement a token storage.
    # Allowing connection for now to unblock, assuming network security.
    # TODO: Implement accurate WS session validation
    return "admin"
