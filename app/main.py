import asyncio
import sys
import logging

# Windows subprocess support requires ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.database import create_db_and_tables
from app.core.security import check_auth, get_user_from_token
from app.services import RunnerService, SchedulerService, AuthService, PlaybookService
from app.models import User
from app.core.onboarding import seed_onboarding_data, seed_users, seed_app_settings
from app.core.database import engine
from sqlmodel import Session, select

# Import Routers
from app.routers import playbooks, history, settings as settings_router, websocket, scheduler as scheduler_router, core, inventory as inventory_router, ssh as ssh_router, templates as templates_router, auth as auth_router, users as users_router

settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)



settings_conf = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages Sible application lifecycle events.

    On Startup:
    - Creates database tables if missing.
    - Cleans up orphaned or dead job processes.
    - Applies global log retention policies.
    - Seeds default admin user and onboarding examples.
    - Starts the background task scheduler.

    On Shutdown:
    - Stops the scheduler and cleans up resources.
    """
    # Startup
    logger.info("Sible starting up...")
    create_db_and_tables()
    
    # Cleanup jobs needs DB session
    with Session(engine) as session:
        RunnerService(session).cleanup_started_jobs()
        
        # Apply global retention policies on startup
        from app.services.history import HistoryService
        HistoryService(session).apply_retention_policies()
        
        # Seed RBAC Users
        seed_users(session)
        
        # Seed App Settings (Favicon etc)
        seed_app_settings(session)
        
        # Seed Onboarding Data
        seed_onboarding_data(session, PlaybookService(session))

    SchedulerService.start()
    logger.info("Sible started successfully.")
    
    yield
    # Shutdown
    logger.info("Sible shutting down...")
    SchedulerService.shutdown()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Global Exception Handlers
@app.exception_handler(HTTPException)
async def htmx_http_exception_handler(request: Request, exc: HTTPException):
    """Returns HTML error partials for HTMX requests, JSON for API calls."""
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content=f'<div class="log-error" style="padding: 1rem;">{exc.detail}</div>',
            status_code=exc.status_code,
        )
    return Response(content=str(exc.detail), status_code=exc.status_code)

@app.exception_handler(Exception)
async def htmx_generic_exception_handler(request: Request, exc: Exception):
    """Catches unhandled exceptions and returns clean error responses."""
    logger.exception("Unhandled exception")
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content='<div class="log-error" style="padding: 1rem;">An unexpected error occurred.</div>',
            status_code=500,
        )
    return Response(content="Internal Server Error", status_code=500)

# Auth Middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next) -> Response:
    """Redirects unauthenticated users to login and injects user context.

    Why: Uses HttpOnly JWT cookies for session security. HTMX requests
    are handled with special headers to trigger client-side redirects
    without reloading the entire page.

    Args:
        request: FastAPI request.
        call_next: Next handler in chain.

    Returns:
        Final application response.
    """
    # Exclude static files, login/logout, and WebSockets from authentication redirect.
    # WebSockets are authenticated internally in their own endpoints.
    if (request.url.path.startswith("/static") or 
        request.url.path.startswith("/ws/") or 
        request.url.path in ["/login", "/logout", "/api/auth/login"]):
        return await call_next(request)

    if not check_auth(request):
        # HTMX requests should probably be redirected to login or show 401
        if request.headers.get("HX-Request") or request.headers.get("HX-Target"):
             response = Response(status_code=200)
             response.headers["HX-Redirect"] = "/login"
             return response
        return RedirectResponse(url="/login")
        
    # Inject user into state for templates
    from app.core.security import get_user_from_token
    token = request.cookies.get("access_token")
    user_obj = None
    if token:
        if token.startswith("Bearer "):
            token = token[7:]
        user_data = get_user_from_token(token)
        if user_data:
            with Session(engine) as session:
                user_obj = session.exec(select(User).where(User.username == user_data["username"])).first()
    
    request.state.user = user_obj

    response = await call_next(request)
    
    # Check for default password warning
    if user_obj:
        from app.core.security import is_using_default_password
        import json
        if is_using_default_password(user_obj):
            existing_trigger = response.headers.get("HX-Trigger", "{}")
            try:
                trigger_data = json.loads(existing_trigger)
            except json.JSONDecodeError:
                trigger_data = {existing_trigger: True} if existing_trigger != "{}" else {}
            
            trigger_data["show-toast"] = {
                "message": "SECURITY WARNING: You are using a default password. Please change it in Settings immediately.",
                "level": "error"
            }
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
            
    return response

# Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings_conf.SECRET_KEY, 
    https_only=False, # Allow HTTP for now
    same_site="lax"
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' ws: wss:;"
    return response

# Mount Static
app.mount("/static", StaticFiles(directory=str(settings_conf.STATIC_DIR)), name="static")

# Include Routers
app.include_router(core.router)
app.include_router(playbooks.router)
app.include_router(history.router)
app.include_router(settings_router.router)
app.include_router(websocket.router)
app.include_router(scheduler_router.router)
app.include_router(inventory_router.router)
app.include_router(ssh_router.router)
app.include_router(templates_router.router)
app.include_router(auth_router.router)
app.include_router(users_router.router)
