from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from contextlib import asynccontextmanager
import os
import traceback

from app.routes import router
from app.tasks import scheduler
from app.database import create_db_and_tables
from app.auth import check_auth
from app.services import RunnerService

import sys
import asyncio

# Fix for Windows subprocess support in asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db_and_tables()
    RunnerService.cleanup_started_jobs()
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# Auth Middleware (Added first, so it is inner)
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    try:
        # List of paths to exclude from auth
        public_paths = ["/login", "/static", "/docs", "/openapi.json", "/favicon.ico"]
        
        # Check if path is public
        is_public = any(request.url.path.startswith(path) for path in public_paths)
        
        if is_public:
            return await call_next(request)
            
        # Check Auth
        if not check_auth(request):
            # HTMX Redirect Support
            if request.headers.get("HX-Request"):
                 return Response(headers={"HX-Redirect": "/login"})
            # Standard Redirect
            return RedirectResponse(url="/login", status_code=303)
            
        return await call_next(request)
    except Exception:
        # Log to file in case stdout is missed
        with open("crash.log", "w") as f:
            traceback.print_exc(file=f)
        traceback.print_exc()
        return Response("Internal Server Error (Check Logs)", status_code=500)

# Session Middleware (Must be added LAST to be OUTERMOST/FIRST to execute)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "sible-secret-key-change-me"), https_only=False)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Mount Static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include Routes
app.include_router(router)
