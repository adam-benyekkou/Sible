from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from typing import Optional
from app.core.database import engine
from sqlmodel import Session, select
import traceback


from jose import jwt, JWTError
from app.core.config import get_settings

settings = get_settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"

async def get_current_user(request: Request) -> str:
    """
    Dependency that checks if the user is authenticated via JWT cookie.
    Returns username if valid, raises 401 otherwise.
    """
    token = request.cookies.get("access_token")
    if not token:
        # Check Authorization header as fallback (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
        
    # Remove "Bearer " prefix if present in cookie (sometimes set that way)
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    user_data = get_user_from_token(token)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user_data["username"]

def get_user_from_token(token: str) -> Optional[dict]:
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
    """
    Synchronous helper for middleware.
    """
    try:
        # We can't use async dependency here easily in synchronous middleware context without async loop
        # But we can verify token manually
        token = request.cookies.get("access_token")
        if not token: 
            return False
            
        if token.startswith("Bearer "):
            token = token[7:]
            
        return get_user_from_token(token) is not None
    except Exception as e:
        print(f"Auth Check Error: {e}")
        traceback.print_exc()
        return False


from fastapi import WebSocket

async def get_current_user_ws(websocket: WebSocket) -> str:
    """
    WebSocket Dependency to check auth via Cookie.
    """
    token = websocket.cookies.get("access_token")
    if not token:
        # Try query param ?token=...
        token = websocket.query_params.get("token")
        
    if not token:
         # Close connection? Or return None?
         # For dependency, we usually raise exception or return None
         # But websocket dependency failure handling is specific
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
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: str = Depends(get_current_user)):
        # Ideally get_current_user returns a User object or we fetch it here.
        # But for now get_current_user returns username string.
        # We need to fetch the role from DB or encode it in token.
        # Token has role! "role": user.role
        # Let's verify token again or fetch user. 
        # Better: Refactor get_current_user to return User object or Dict with role.
        # For MVP, let's fetch user from DB to be checking fresh permissions.
        with Session(engine) as session:
            from app.models import User
            statement = select(User).where(User.username == user)
            db_user = session.exec(statement).first()
            if not db_user:
                 raise HTTPException(status_code=401, detail="User not found")
            
            if db_user.role not in self.allowed_roles and "admin" not in db_user.role: # Admin always allowed? Or explicit?
                 # If user is admin, they should pass? 
                 # Let's say Admin is always allowed for everything?
                 if db_user.role == UserRole.ADMIN:
                     return db_user
                     
                 raise HTTPException(status_code=403, detail="Operation not permitted")
            return db_user


