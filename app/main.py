import asyncio
import sys

# Windows subprocess support requires ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("Sible: Windows Proactor Event Loop Policy set.")

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import traceback

from app.core.config import get_settings
from app.core.database import create_db_and_tables
from app.core.security import check_auth
from app.services import RunnerService, SchedulerService, SettingsService, AuthService
from app.models import User
from app.core.database import engine
from sqlmodel import Session, select

# Import Routers
from app.routers import playbooks, history, settings as settings_router, websocket, scheduler as scheduler_router, core, inventory as inventory_router, ssh as ssh_router, templates as templates_router, auth as auth_router, users as users_router



settings_conf = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):


    # Startup
    create_db_and_tables()
    
    # Cleanup jobs needs DB session
    with Session(engine) as session:
        RunnerService(session).cleanup_started_jobs()
        
        # Ensure Admin User
        auth_service = AuthService(session)
        if not auth_service.authenticate_user("admin", "admin"): # Check if default exists/works? No, check existence by username
            stmt = select(User).where(User.username == "admin")
            admin_exists = session.exec(stmt).first()
            if not admin_exists:
                 print("Creating default admin user...")
                 auth_service.create_user("admin", "admin", "admin")

    SchedulerService.start()
    
    yield
    # Shutdown
    SchedulerService.shutdown()

app = FastAPI(lifespan=lifespan)

# Auth Middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/static") or request.url.path in ["/login", "/logout", "/api/auth/login"]:
        return await call_next(request)
    
    # Inject user into state for templates
    from app.core.security import get_user_from_token
    token = request.cookies.get("access_token")
    user_data = None
    if token:
         if token.startswith("Bearer "):
            token = token.split(" ")[1]
         user_data = get_user_from_token(token)
    
    if user_data:
        request.state.user = user_data
    else:
        request.state.user = None


    if not check_auth(request):
        # HTMX requests should probably be redirected to login or show 401
        if request.headers.get("HX-Request") or request.headers.get("HX-Target"):
             response = Response(status_code=200)
             response.headers["HX-Redirect"] = "/login"
             return response
        return RedirectResponse(url="/login")
        
    response = await call_next(request)
    return response

# Session Middleware
app.add_middleware(SessionMiddleware, secret_key=settings_conf.SECRET_KEY, https_only=False)

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
