from fastapi import APIRouter, Request, Response, Form, Depends
from app.templates import templates
from app.core.config import get_settings
from app.dependencies import get_playbook_service, get_runner_service
from app.services import PlaybookService, RunnerService, LinterService
from app.utils.htmx import trigger_toast
import json

settings = get_settings()
router = APIRouter()

@router.get("/playbooks/{name:path}")
async def get_playbook_view(
    name: str, 
    request: Request, 
    service: PlaybookService = Depends(get_playbook_service)
):
    content = service.get_playbook_content(name)
    if content is None:
        return Response(content="<p>File not found</p>", media_type="text/html")
    
    context = {
        "request": request, 
        "name": name, 
        "content": content,
        "has_requirements": service.has_requirements(name)
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/editor.html", context)
    
    return templates.TemplateResponse("playbook_view.html", context)

@router.post("/playbooks/{name:path}")
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

@router.post("/playbooks")
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

@router.delete("/playbooks/{name:path}")
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
    form = await request.form()
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "run",
        "limit": form.get("limit"),
        "tags": form.get("tags"),
        "verbosity": form.get("verbosity"),
        "extra_vars": form.get("extra_vars")
    })

@router.post("/check/{name:path}")
async def check_playbook_endpoint(name: str, request: Request):
    form = await request.form()
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "check",
        "limit": form.get("limit"),
        "tags": form.get("tags"),
        "verbosity": form.get("verbosity"),
        "extra_vars": form.get("extra_vars")
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
@router.post("/playbook/{name:path}/install-requirements")
async def install_requirements_endpoint(
    name: str,
    request: Request,
    service: RunnerService = Depends(get_runner_service)
):
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "install-requirements"
    })

# Template Library Endpoints

# api/templates CRUD is handled in app.routers.templates


@router.post("/api/templates/use")
async def use_template(
    request: Request,
    service: PlaybookService = Depends(get_playbook_service)
):
    """
    Instantiates a template into a new playbook.
    Query params: ?path=system/update.yaml
    """
    path = request.query_params.get("path")
    if not path:
        response = Response(status_code=200)
        trigger_toast(response, "No template specified", "error")
        return response

    from app.services.template import TemplateService
    content = TemplateService.get_template_content(path)
    if not content:
        response = Response(status_code=200)
        trigger_toast(response, "Template not found", "error")
        return response

    # Generate unique name
    import time
    name_clean = path.split("/")[-1].replace(".yaml", "").replace(".yml", "")
    timestamp = int(time.time())
    new_filename = f"{name_clean}_{timestamp}.yaml"
    
    success = service.create_playbook(new_filename)
    if not success: # Should unlikely happen with timestamp
        response = Response(status_code=200)
        trigger_toast(response, "Failed to create file", "error")
        return response

    service.save_playbook_content(new_filename, content)
    
    # Redirect to editor
    response = Response(status_code=200)
    response.headers["HX-Redirect"] = f"/playbooks/{new_filename}"
    trigger_toast(response, f"Created from {name_clean}", "success")
    return response

from pydantic import BaseModel
from typing import Optional

from app.schemas.playbook import CreatePlaybookRequest

@router.post("/api/playbooks/create")
async def create_playbook_api(
    payload: CreatePlaybookRequest,
    service: PlaybookService = Depends(get_playbook_service)
):
    """
    Creates a new playbook with optional folder and template.
    """
    import os
    
    # Construct path
    folder = payload.folder.strip("/\\") if payload.folder else ""
    filename = payload.name
    if not filename.endswith((".yaml", ".yml")):
        filename += ".yaml"
        
    full_path = f"{folder}/{filename}" if folder else filename
    
    # Check if exists
    # validate_path checks existence via _validate_path but checking existence is explicitly done in create_playbook
    # We should let service handle creation, but service.create_playbook returns False if exists.
    
    content = None
    if payload.template_id:
        from app.services.template import TemplateService
        content = TemplateService.get_template_content(payload.template_id)
        if not content:
            response = Response(status_code=200)
            trigger_toast(response, "Template not found", "error")
            return response

    if content:
        # Create with content
        # service.create_playbook writes default content. 
        # We can try to use save_playbook_content directly, but we want to ensure we don't overwrite if exists.
        # But save_playbook_content doesn't check "if exists return false".
        # Let's rely on create_playbook first to ensure file creation (and checks) then overwrite?
        # Or better: check existence first explicitly.
        
        # Taking a shortcut: create_playbook returns False if exists.
        if not service.create_playbook(full_path):
             response = Response(status_code=200)
             trigger_toast(response, "File already exists or invalid path", "error")
             return response
             
        # Overwrite with template content
        service.save_playbook_content(full_path, content)
    else:
        # Create blank
        if not service.create_playbook(full_path):
             response = Response(status_code=200)
             trigger_toast(response, "File already exists or invalid path", "error")
             return response

    response = Response(status_code=200)
    # HX-Redirect to the new file
    response.headers["HX-Redirect"] = f"/playbooks/{full_path}"
    trigger_toast(response, f"Created {full_path}", "success")
    return response
