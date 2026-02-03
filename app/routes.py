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

import json

# Helper for Toast Headers
def trigger_toast(response: Response, message: str, level: str = "success"):
    trigger_data = {
        "show-toast": {
            "message": message,
            "level": level
        }
    }
    # If a trigger already exists, we might need to merge, but for now we assume single trigger or append
    # But FastAPI headers are case-insensitive dicts.
    # To be safe with multiple triggers (like refresh + toast), we can merge them if needed.
    # Here we'll just handle sidebar-refresh manually in the same dict if needed.
    
    current_trigger = response.headers.get("HX-Trigger")
    if current_trigger:
        try:
            # If it's already JSON
            current_dict = json.loads(current_trigger)
            current_dict.update(trigger_data)
            response.headers["HX-Trigger"] = json.dumps(current_dict)
        except:
            # If it's a simple string (like "sidebar-refresh")
            trigger_data[current_trigger] = True
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
    else:
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

@router.post("/playbook/{name}")
async def save_playbook(name: str, request: Request):
    form = await request.form()
    content = form.get("content")
    if content is None:
        response = Response(status_code=200) # Use 200 so HTMX processes headers
        trigger_toast(response, "Missing content", "error")
        return response
    
    success = PlaybookService.save_playbook_content(name, content)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to save file", "error")
        return response
    
    response = Response("Saved successfully")
    trigger_toast(response, "Playbook saved", "success")
    return response

@router.post("/playbook")
async def create_playbook(request: Request):
    name = request.headers.get("HX-Prompt")
    
    if not name:
        response = Response(status_code=200)
        trigger_toast(response, "Playbook name is required", "error")
        return response
    
    success = PlaybookService.create_playbook(name)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to create (Invalid name or exists)", "error")
        return response
    
    response = Response(status_code=200)
    # Trigger refresh AND toast
    response.headers["HX-Trigger"] = json.dumps({
        "sidebar-refresh": True,
        "show-toast": {
            "message": f"Playbook '{name}' created", 
            "level": "success"
        }
    })
    return response

@router.delete("/playbook/{name}")
async def delete_playbook(name: str):
    success = PlaybookService.delete_playbook(name)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to delete playbook", "error")
        return response
    
    content = """
    <div id="main-content" class="container text-center flex-center h-100" style="color: #868e96;">
        <p>Select a playbook to get started</p>
    </div>
    """
    response = Response(content=content, media_type="text/html")
    response.headers["HX-Trigger"] = json.dumps({
        "sidebar-refresh": True,
        "show-toast": {
            "message": f"Playbook '{name}' deleted", 
            "level": "success"
        }
    })
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
