from sqlmodel import select
from app.models import Host
from typing import Optional
from fastapi import APIRouter, Request, Response, Depends
from typing import List, Optional, Any
from app.templates import templates
from app.core.config import get_settings
from app.dependencies import get_history_service, requires_role
from app.models import User
from app.services import HistoryService
from app.utils.htmx import trigger_toast

settings = get_settings()
router = APIRouter()

@router.get("/history")
async def get_history_page(
    request: Request,
    page: int = 1,
    search: Optional[str] = None,
    status: Optional[str] = None,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Renders the execution history page with filters and pagination.

    Why: Provides a central audit trail for all playbook executions,
    supporting fuzzy search and status-based filtering for easier
    troubleshooting.

    Args:
        request: FastAPI request.
        page: Page number for historical records.
        search: Fuzzy search for playbook names.
        status: Exact status filter (success, failed, running).
        service: Injected HistoryService.
        current_user: Authenticated user (watcher+).

    Returns:
        Full page or partial table template response.
    """
    limit = 20
    offset = (page - 1) * limit
    runs, total_count, users = service.get_recent_runs(limit=limit, offset=offset, search=search, status=status)
    
    # Get groups for UI distinction in Target column
    from sqlmodel import select, func
    from app.models import Host
    groups = service.db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()
    groups.append("all")
    
    import math
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1
    
    context = {
        "request": request, 
        "runs": runs, 
        "active_tab": "history",
        "search": search,
        "status": status or 'all',
        "page": page,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_count": total_count,
        "groups": groups,
        "users": {u.username: u for u in users}
    }
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/history_table.html", context)
        
    return templates.TemplateResponse("history.html", context)

@router.delete("/history/all")
def delete_all_history(
    request: Request,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role("admin"))
) -> Response:
    """Bulk deletes history records matching the current UI filters.

    Args:
        request: Request containing query params or form data for filters.
        service: Injected HistoryService.
        current_user: Admin access required.

    Returns:
        Response with refresh trigger.
    """
    # HTMX hx-delete might send params in query or body depending on hx-include behavior
    search = request.query_params.get("search")
    status = request.query_params.get("status")
    
    if search is None or status is None:
        # Note: HTMX hx-delete doesn't easily send form data in body without extra config,
        # but we check both just in case.
        if search is None: search = request.query_params.get("search")
        if status is None: status = request.query_params.get("status")

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Deleting filtered history: search='{search}', status='{status}'")
    service.delete_all_runs(search=search, status=status)
    response = Response(status_code=200)
    response.headers["HX-Refresh"] = "true"
    return response

@router.delete("/history/run/{run_id}")
async def delete_run(
    run_id: int,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role("admin"))
) -> Response:
    """Permanently deletes a single specific job run record.

    Args:
        run_id: Primary key of the job run.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Response with status 200 or 404.
    """
    success = service.delete_run(run_id)
    if success:
        return Response(status_code=200)
    return Response(status_code=404)

@router.get("/api/history/debug/{run_id}")
async def debug_run_status(
    run_id: int,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
):
    """Debug endpoint to see raw job data."""
    run = service.get_run(run_id)
    if not run:
        return {"error": "Run not found"}
    return {
        "id": run.id,
        "playbook": run.playbook,
        "status": run.status,
        "start_time": str(run.start_time),
        "end_time": str(run.end_time) if run.end_time else None,
        "exit_code": run.exit_code,
        "trigger": run.trigger
    }

@router.get("/api/history/status/{run_id}")
async def get_run_status(
    run_id: int,
    request: Request,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Returns the updated row for a job run, used for polling running jobs.

    Args:
        run_id: Target run ID.
        request: Request object.
        service: Injected service.
        current_user: Authenticated user.

    Returns:
        Partial template with the updated row HTML.
    """
    run = service.get_run(run_id)
    if not run:
        return Response("Run not found", status_code=404)
    
    # Get groups for UI distinction in Target column
    from sqlmodel import select
    from app.models import Host
    groups = service.db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()
    groups.append("all")
    
    # Get user info
    _, _, users = service.get_recent_runs(limit=1, offset=0)
    
    return templates.TemplateResponse("partials/history_rows.html", {
        "request": request,
        "runs": [run],
        "groups": groups,
        "users": {u.username: u for u in users}
    })

@router.get("/history/run/{run_id}")
async def get_run_details(
    run_id: int, 
    request: Request,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Returns the log output and metadata for a specific run in a modal.

    Args:
        run_id: Target run ID.
        request: Request object.
        service: Injected service.
        current_user: Authenticated user.

    Returns:
        Partial template for the log viewer modal.
    """
    run = service.get_run(run_id)
    if not run: return Response("Run not found", status_code=404)
    return templates.TemplateResponse("partials/log_viewer_modal.html", {"request": request, "run": run})

@router.get("/history/{name:path}")
async def get_playbook_history(
    name: str,
    request: Request,
    page: int = 1,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
):
    limit = 20
    offset = (page - 1) * limit
    runs, total_count, users = service.get_playbook_runs(name, limit=limit, offset=offset)
    
    import math
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1

    from sqlmodel import select
    from app.models import Host
    groups = service.db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()
    groups.append("all")

    return templates.TemplateResponse("partials/history_list_modal.html", {
        "request": request,
        "playbook_name": name,
        "manual_runs": runs,
        "page": page,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_count": total_count,
        "groups": groups,
        "users": {u.username: u for u in users}
    })

@router.delete("/history/playbook/{name:path}/all")
async def delete_playbook_history(
    name: str,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role("admin"))
) -> Response:
    """Bulk deletes all history for a specific playbook.

    Args:
        name: Relative path to the playbook.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Response with toast and refresh trigger.
    """
    service.delete_playbook_runs(name)
    response = Response(status_code=200)
    trigger_toast(response, f"History for {name} cleared", "success")
    response.headers["HX-Refresh"] = "true"
    return response
