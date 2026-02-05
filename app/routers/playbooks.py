from fastapi import APIRouter, Request, Response, Form, Depends
from app.templates import templates
from app.config import get_settings
from app.dependencies import get_playbook_service, get_runner_service
from app.services import PlaybookService, RunnerService, LinterService
from app.utils.htmx import trigger_toast
import json

settings = get_settings()
router = APIRouter()

@router.get("/playbook/{name:path}")
async def get_playbook_view(
    name: str, 
    request: Request, 
    service: PlaybookService = Depends(get_playbook_service)
):
    content = service.get_playbook_content(name)
    if content is None:
        return Response(content="<p>File not found</p>", media_type="text/html")
    return templates.TemplateResponse("partials/editor.html", {
        "request": request, 
        "name": name, 
        "content": content,
        "has_requirements": service.has_requirements(name)
    })

@router.post("/playbook/{name:path}")
async def save_playbook(
    name: str, 
    request: Request, 
    service: PlaybookService = Depends(get_playbook_service)
):
    form = await request.form()
    content = form.get("content")
    if content is None:
        response = Response(status_code=200)
        trigger_toast(response, "Missing content", "error")
        return response
    
    success = service.save_playbook_content(name, content)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to save file", "error")
        return response
    
    response = Response("Saved successfully")
    trigger_toast(response, "Playbook saved", "success")
    return response

@router.post("/playbook")
async def create_playbook(
    request: Request,
    service: PlaybookService = Depends(get_playbook_service)
):
    name = request.headers.get("HX-Prompt")
    if not name:
        response = Response(status_code=200)
        trigger_toast(response, "Playbook name is required", "error")
        return response
    
    success = service.create_playbook(name)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to create (Invalid name or exists)", "error")
        return response
    
    response = Response(status_code=200)
    response.headers["HX-Trigger"] = json.dumps({
        "sidebar-refresh": True,
        "show-toast": {
            "message": f"Playbook '{name}' created", 
            "level": "success"
        }
    })
    return response

@router.delete("/playbook/{name:path}")
async def delete_playbook(
    name: str,
    service: PlaybookService = Depends(get_playbook_service)
):
    success = service.delete_playbook(name)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to delete playbook", "error")
        return response
    
    content = '<div id="main-content" class="container text-center flex-center h-100" style="color: #868e96;"><p>Select a playbook to get started</p></div>'
    response = Response(content=content, media_type="text/html")
    response.headers["HX-Trigger"] = json.dumps({
        "sidebar-refresh": True,
        "show-toast": {
            "message": f"Playbook '{name}' deleted", 
            "level": "success"
        }
    })
    return response

@router.post("/run/{name:path}")
async def run_playbook_endpoint(name: str, request: Request):
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "run"
    })

@router.post("/check/{name:path}")
async def check_playbook_endpoint(name: str, request: Request):
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "check"
    })

@router.post("/stop/{name:path}")
async def stop_playbook_endpoint(
    name: str,
    service: RunnerService = Depends(get_runner_service)
):
    success = service.stop_playbook(name)
    if success:
        response = Response(status_code=200)
        trigger_toast(response, "Stopping playbook...", "info")
        return response
    response = Response(status_code=200)
    trigger_toast(response, "Process not found or already stopped", "error")
    return response

@router.post("/lint")
async def lint_playbook(request: Request):
    form = await request.form()
    content = form.get("content")
    if not content: return []
    return await LinterService.lint_playbook_content(content)
