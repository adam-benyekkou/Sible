from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from app.services import SettingsService

async def get_current_user(request: Request):
    """
    Dependency that checks if the user is authenticated via session.
    If auth is disabled, allow access.
    If auth is enabled and no session, redirect to /login (via exception or return None).
    """
    settings = SettingsService.get_settings()
    
    # If Auth is disabled, everyone is "authenticated"
    if not settings.auth_enabled:
        return "admin"
        
    user = request.session.get("user")
    if not user:
        # If accessing an API/HTMX endpoint, return 401
        if "hx-request" in request.headers or request.url.path.startswith("/api/"):
             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
        # For page loads, we want to redirect, but dependencies can't easily return RedirectResponse 
        # to the route handler directly without raising.
        # We'll rely on the route handler or a middleware to catch this, OR
        # better yet, we simply raise an HTTP exception that we catch in global exception handler? 
        # Or, we just use a helper function in routes instead of a pure dependency for redirects.
        # Let's try raising an HTTPException and catching it in main.py? 
        # actually, standard pattern is `raise HTTPException(status_code=401)` and redirect.
        # But for simplicity in `routes.py`, we can check:
        # user = await get_current_user(req); if not user: return Redirect...
        return None 
        
    return user

def check_auth(request: Request) -> bool:
    """Helper to check check auth status boolean"""
    settings = SettingsService.get_settings()
    if not settings.auth_enabled:
        return True
    return request.session.get("user") is not None
