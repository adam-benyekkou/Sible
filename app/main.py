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
    return templates.TemplateResponse("index.html", {"request": request})

# Placeholder for sidebar HTMX
from app.services import PlaybookService

@app.get("/partials/sidebar")
async def get_sidebar(request: Request):
    playbooks = PlaybookService.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {"request": request, "playbooks": playbooks})

@app.get("/playbook/{name}")
async def get_playbook_view(name: str, request: Request):
    content = PlaybookService.get_playbook_content(name)
    if content is None:
        return "<p>File not found</p>"
    
    return templates.TemplateResponse("partials/editor.html", {
        "request": request, 
        "name": name, 
        "content": content
    })

@app.post("/playbook/{name}")
async def save_playbook(name: str, request: Request):
    form = await request.form()
    content = form.get("content")
    if content is None:
        return "Missing content", 400
    
    success = PlaybookService.save_playbook_content(name, content)
    if not success:
        return "Failed to save", 500
    
    return "Saved successfully"
