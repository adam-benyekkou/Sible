from fastapi import APIRouter, Request, Response, Form, Depends, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates
from app.services.auth import AuthService
from app.dependencies import get_db
from sqlmodel import Session
from datetime import timedelta

router = APIRouter(tags=["auth"])

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    """Renders the login page.

    Args:
        request: FastAPI request.

    Returns:
        TemplateResponse for the login page.
    """
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/api/auth/login")
async def login_api(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
) -> Response:
    """Handles user login and issues an HttpOnly JWT cookie.

    Why: Uses HttpOnly cookies to prevent XSS attacks while maintaining a
    stateless authentication flow. Redirects to the dashboard on success.

    Args:
        request: FastAPI request.
        response: Response object to attach the cookie to.
        username: Provided username.
        password: Provided raw password.
        db: Database session.

    Returns:
        RedirectResponse on success, or 401 Unauthorized with login template.
    """
    service = AuthService(db)
    user = service.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=status.HTTP_401_UNAUTHORIZED)
    
    # Create Token
    access_token = service.create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    
    # Set Cookie
    redirect = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=60 * 60 * 24, # 1 day
        samesite="lax"
    )
    return redirect

@router.get("/api/auth/logout")
async def logout(response: Response) -> Response:
    """Logs out the user by deleting the session cookie.

    Args:
        response: Response object.

    Returns:
        RedirectResponse to the login page.
    """
    redirect = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie("access_token")
    return redirect
