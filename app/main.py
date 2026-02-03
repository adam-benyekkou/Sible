from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
PLAYBOOKS_DIR = BASE_DIR / "playbooks"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount Static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("layout.html", {"request": request})

# Placeholder for sidebar HTMX
@app.get("/partials/sidebar")
async def get_sidebar(request: Request):
    # Mock data for now
    playbooks = [
        {"name": "deploy_web.yaml", "status": "idle"},
        {"name": "update_db.yaml", "status": "running"},
    ]
    # In reality we would render a partial template loop
    # For now, let's return a simple HTML string to verify wiring
    html = ""
    for pb in playbooks:
        status_class = "running" if pb['status'] == 'running' else ""
        html += f"""
        <div class="playbook-item">
            <div class="status-dot {status_class}"></div>
            {pb['name']}
        </div>
        """
    return html
