from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.services import PlaybookService, RunnerService
import asyncio

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/partials/sidebar")
async def get_sidebar(request: Request):
    playbooks = PlaybookService.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {"request": request, "playbooks": playbooks})

@router.get("/playbook/{name}")
async def get_playbook_view(name: str, request: Request):
    content = PlaybookService.get_playbook_content(name)
    if content is None:
        return Response(content="<p>File not found</p>", media_type="text/html")
    
    return templates.TemplateResponse("partials/editor.html", {
        "request": request, 
        "name": name, 
        "content": content
    })

@router.post("/playbook/{name}")
async def save_playbook(name: str, request: Request):
    form = await request.form()
    content = form.get("content")
    if content is None:
        return Response("Missing content", status_code=400)
    
    success = PlaybookService.save_playbook_content(name, content)
    if not success:
        return Response("Failed to save", status_code=500)
    
    return Response("Saved successfully")

@router.post("/playbook")
async def create_playbook(request: Request):
    # HTMX prompt sends value in "hx-prompt" header? No, usually in a prompt or we use hx-vals.
    # Standard hx-prompt sends it as data?
    # Actually, hx-prompt sends the value in the headers as `HX-Prompt` AND as a parameter?
    # Documentation says: "The user input will be sent in a header called HX-Prompt"
    
    name = request.headers.get("HX-Prompt")
    
    if not name:
        return Response("Name is required", status_code=400)
    
    success = PlaybookService.create_playbook(name)
    if not success:
        return Response("Failed to create playbook (Invalid name or already exists)", status_code=400)
    
    # Trigger sidebar refresh
    response = Response(status_code=200)
    response.headers["HX-Trigger"] = "sidebar-refresh"
    return response

@router.delete("/playbook/{name}")
async def delete_playbook(name: str):
    success = PlaybookService.delete_playbook(name)
    if not success:
        return Response("Failed to delete", status_code=400)
    
    # Return empty content for the editor area and trigger sidebar refresh
    content = """
    <div id="main-content" class="container text-center flex-center h-100" style="color: #868e96;">
        <p>Select a playbook to get started</p>
    </div>
    """
    response = Response(content=content, media_type="text/html")
    response.headers["HX-Trigger"] = "sidebar-refresh"
    return response
@router.post("/run/{name}")
async def run_playbook_endpoint(name: str, request: Request):
    """
    Triggers the playbook execution on the frontend.
    Instead of running it here, we return HTML that connects to the SSE stream.
    """
    # We return the "Running..." state UI which includes the hx-ext="sse" connection
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name
    })

@router.get("/stream/{name}")
async def stream_playbook_endpoint(name: str):
    """
    SSE Endpoint.
    """
    async def event_generator():
        yield "event: start\ndata: Connected to stream\n\n"
        async for line in RunnerService.run_playbook(name):
            # Server-Sent Events format: "data: <payload>\n\n"
            # We must handle newlines in the data carefully or just send line by line
            yield f"data: {line}\n\n"
        yield "event: end\ndata: Execution finished\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
