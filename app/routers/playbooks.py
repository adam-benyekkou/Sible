from fastapi import APIRouter, Request, Response, Form, Depends, Query
from fastapi.responses import HTMLResponse
from typing import Any, List, Optional
from app.templates import templates
from app.core.config import get_settings
from app.dependencies import get_playbook_service, get_runner_service, requires_role, check_default_password
from app.services import PlaybookService, RunnerService, LinterService
from app.models import User
from app.utils.htmx import trigger_toast
import json

settings = get_settings()
router = APIRouter()
@router.get("/playbooks/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    request: Request,
    page: int = 1,
    playbook_service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"])),
    show_default_password_warning: bool = Depends(check_default_password)
) -> Response:
    """Renders the main playbook dashboard.

    Args:
        request: FastAPI request.
        page: Current page number.
        playbook_service: Injected service for metadata.
        current_user: Authenticated user.
        show_default_password_warning: Whether to show the default password warning.

    Returns:
        TemplateResponse for the dashboard.
    """
    limit = 20
    offset = (page - 1) * limit
    playbooks, total_count = playbook_service.get_playbooks_metadata(user_id=current_user.id, limit=limit, offset=offset)
    
    import math
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1
    
    return templates.TemplateResponse("playbooks_dashboard.html", {
        "request": request,
        "playbooks": playbooks,
        "page": page,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_count": total_count,
        "show_default_password_warning": show_default_password_warning
    })

@router.get("/api/playbooks/list")
async def list_playbooks_api(
    request: Request,
    page: int = 1,
    search: Optional[str] = Query(None),
    playbook_service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Returns a paginated list of playbooks as an HTML table fragment."""
    limit = 20
    offset = (page - 1) * limit
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"API Request to list playbooks. search={search}, user={current_user.username}")
    
    playbooks, total_count = playbook_service.get_playbooks_metadata(search=search, user_id=current_user.id, limit=limit, offset=offset)
    
    logger.info(f"API Returning {len(playbooks)} playbooks. Total count: {total_count}")
    
    import math
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1
    
    return templates.TemplateResponse("partials/playbooks_table.html", {
        "request": request,
        "playbooks": playbooks,
        "page": page,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_count": total_count,
        "search": search
    })
    
    import math
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1
    
    return templates.TemplateResponse("partials/playbooks_table.html", {
        "request": request,
        "playbooks": playbooks,
        "page": page,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_count": total_count,
        "search": search
    })

@router.post("/api/playbooks/toggle-favorite")
async def toggle_favorite(
    request: Request,
    playbook_path: str = Form(...),
    playbook_service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Toggles a playbook's favorite status and returns updated UI components.

    Why: Returns two fragments (icon and sidebar) for HTMX Out-of-Band (OOB) updates,
    ensuring the UI stays in sync without a full page reload.

    Args:
        request: Request object.
        playbook_path: Path to the playbook.
        playbook_service: Injected service.
        current_user: Current user.

    Returns:
        Response containing concatenated HTML fragments.
    """
    is_favorited = playbook_service.toggle_favorite(playbook_path, current_user.id)
    
    # Render updated heart icon
    icon_content = templates.TemplateResponse("partials/favorite_icon.html", {
        "request": request,
        "playbook": {"path": playbook_path, "is_favorited": is_favorited}
    }).body.decode()

    # Also render favorites list for OOB update
    all_playbooks, _ = playbook_service.get_playbooks_metadata(user_id=current_user.id)
    favorites = [p for p in all_playbooks if p["is_favorited"]]
    from collections import defaultdict
    grouped = defaultdict(list)
    for p in favorites:
        grouped[p["folder"] or "Root"].append(p)
    
    sidebar_content = templates.TemplateResponse("partials/sidebar_favorites.html", {
        "request": request,
        "favorites_grouped": dict(grouped),
        "oob": True
    }).body.decode()

    return Response(content=f"{icon_content}\n{sidebar_content}", media_type="text/html")

@router.get("/api/sidebar/favorites")
async def get_sidebar_favorites(
    request: Request,
    playbook_service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Renders the sidebar fragment containing favorited playbooks.

    Args:
        request: Request object.
        playbook_service: Injected service.
        current_user: Current user.

    Returns:
        TemplateResponse for the sidebar favorites.
    """
    all_playbooks, _ = playbook_service.get_playbooks_metadata(user_id=current_user.id)
    favorites = [p for p in all_playbooks if p["is_favorited"]]
    
    # Group by folder
    from collections import defaultdict
    grouped = defaultdict(list)
    for p in favorites:
        grouped[p["folder"] or "Root"].append(p)
    
    return templates.TemplateResponse("partials/sidebar_favorites.html", {
        "request": request,
        "favorites_grouped": dict(grouped)
    })

@router.delete("/api/playbooks/bulk")
async def delete_playbooks_bulk(
    names: List[str] = Query(...),
    playbook_service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role("admin"))
) -> Response:
    """Bulk deletes selected playbooks from the filesystem.

    Args:
        names: List of paths to delete.
        playbook_service: Injected service.
        current_user: Admin access required.

    Returns:
        No Content response with HTMX trigger for refresh.
    """
    success = playbook_service.delete_playbooks_bulk(names)
    if success:
        return Response(status_code=204, headers={"HX-Trigger": "sidebar-refresh, playbooks-refresh"})
    return Response(status_code=500)



@router.get("/api/playbook-vars/{name:path}")
async def get_playbook_variables_form(
    name: str,
    request: Request,
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Extracts variables from a playbook and returns an HTML form.

    Why: Sible parses playbook YAML to find 'vars' and placeholders,
    dynamically generating form inputs for the run modal.

    Args:
        name: Playbook path.
        request: Request object.
        service: Injected service.
        current_user: Operator or admin.

    Returns:
        Partial template for the variable input form.
    """
    from app.services.settings import SettingsService
    settings_service = SettingsService(service.db)
    env_vars = settings_service.get_env_vars()
    secrets = [v for v in env_vars if v.is_secret]
    
    variables = service.get_playbook_variables(name)
    
    return templates.TemplateResponse("partials/variable_inputs.html", {
        "request": request,
        "variables": variables,
        "secrets": secrets
    })

@router.get("/playbooks/{name:path}")
async def get_playbook_view(
    name: str, 
    request: Request, 
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"])),
    show_default_password_warning: bool = Depends(check_default_password)
) -> Response:
    """Renders the playbook editor view or returns the partial editor fragment.

    Args:
        name: Relative path to the playbook.
        request: Request object.
        service: Injected service.
        current_user: Authenticated user.
        show_default_password_warning: Whether to show the default password warning.

    Returns:
        Full page or partial editor template.
    """
    content = service.get_playbook_content(name)
    if content is None:
        return Response(content="<p>File not found</p>", media_type="text/html")
    
    context = {
        "request": request, 
        "name": name, 
        "content": content,
        "has_requirements": service.has_requirements(name),
        "show_default_password_warning": show_default_password_warning
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/editor.html", context)
    
    return templates.TemplateResponse("playbook_view.html", context)

@router.post("/playbooks/{name:path}")
async def save_playbook(
    name: str, 
    request: Request, 
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Saves the modified content of a playbook.

    Args:
        name: Playbook path.
        request: Request containing 'content' form data.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Response with success/error toast.
    """
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
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Creates a new empty playbook based on an HTMX prompt.

    Args:
        request: Request with 'HX-Prompt' header.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Response with refresh trigger and toast.
    """
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
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Deletes a playbook from the filesystem.

    Args:
        name: Playbook path.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Content fragment with refresh trigger and toast.
    """
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
async def run_playbook_endpoint(
    name: str, 
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Initiates a playbook run and renders the terminal connector UI.

    Why: This endpoint captures run parameters (limit, tags, vars) and
    prepares the UI to establish an SSE connection for log streaming.

    Args:
        name: Playbook path.
        request: Request with form parameters.
        current_user: Operator or admin.

    Returns:
        Partial template for the terminal connector.
    """
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

@router.get("/api/playbooks/run-modal/{name:path}")
async def get_run_modal(
    name: str,
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Returns the partial HTML for the execution configuration modal.

    Args:
        name: Path to the target playbook.
        request: Request object.
        current_user: Authenticated operator+.

    Returns:
        Modal template response.
    """
    return templates.TemplateResponse("partials/playbook_run_modal.html", {
        "request": request,
        "name": name
    })

@router.post("/check/{name:path}")
async def check_playbook_endpoint(
    name: str, 
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Initiates an Ansible check run (dry-run).

    Args:
        name: Playbook path.
        request: Request object.
        current_user: Authenticated operator+.

    Returns:
        Partial template for the terminal connector in check mode.
    """
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
    service: RunnerService = Depends(get_runner_service),
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Attempts to terminate a running playbook process.

    Args:
        name: Path to the running playbook.
        service: Injected runner service.
        current_user: Authenticated operator+.

    Returns:
        Response with termination status toast.
    """
    success = service.stop_playbook(name)
    if success:
        response = Response(status_code=200)
        trigger_toast(response, "Stopping playbook...", "info")
        return response
    response = Response(status_code=200)
    trigger_toast(response, "Process not found or already stopped", "error")
    return response

@router.post("/lint")
async def lint_playbook(
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> List[Any]:
    """Lints raw playbook content using ansible-lint if available.

    Args:
        request: Request with 'content' form field.
        current_user: Authenticated operator+.

    Returns:
        List of linting errors or empty list.
    """
    form = await request.form()
    content = form.get("content")
    if not content: return []
    return await LinterService.lint_playbook_content(content)

@router.post("/playbook/{name:path}/install-requirements")
async def install_requirements_endpoint(
    name: str,
    request: Request,
    service: RunnerService = Depends(get_runner_service),
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Triggers 'ansible-galaxy install' for a playbook's requirements.

    Args:
        name: Playbook path.
        request: Request object.
        service: Injected service.
        current_user: Authenticated operator+.

    Returns:
        Terminal connector UI fragment for SSE streaming.
    """
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
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Instantiates a template into a new playbook.

    Why: Allows users to bootstrap new playbooks from pre-defined patterns
    (e.g., standard patching or user creation).

    Args:
        request: Request with 'path' query parameter for the template.
        service: Injected service for saving the new file.
        current_user: Admin access required.

    Returns:
        No Content response with HTMX redirect to the new playbook.
    """
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

from app.schemas.playbook import CreatePlaybookRequest

@router.post("/api/playbooks/create")
async def create_playbook_api(
    payload: CreatePlaybookRequest,
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """API endpoint to create a playbook with folder support and optional templates.

    Why: Provides a more robust alternative to the simple prompt-based creation,
    supporting nested directories and template selection in a single call.

    Args:
        payload: Pydantic model with name, folder, and template info.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Response with HTMX redirect to the new playbook editor.
    """
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
