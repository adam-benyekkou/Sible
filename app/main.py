from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routes import router
from app.tasks import setup_scheduler

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Mount Static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include Routes
app.include_router(router)

# Setup Scheduler (Placeholder)
setup_scheduler()
