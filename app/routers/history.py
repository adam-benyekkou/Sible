from fastapi import APIRouter, Request, Response, Depends
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
    search: str = None,
    status: str = None,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
):
    limit = 20
    offset = (page - 1) * limit
    runs, total_count = service.get_recent_runs(limit=limit, offset=offset, search=search, status=status)
    
    # Get groups for UI distinction in Target column
    from sqlmodel import select
    from app.models import Host
    from app.dependencies import get_db
    # We can use the service or just a quick query
    db = next(get_db())
    groups = list(set(h.group_name for h in db.exec(select(Host)).all() if h.group_name))
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
        "groups": groups
    }
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/history_table.html", context)
        
    return templates.TemplateResponse("history.html", context)

@router.delete("/history/all")
async def delete_all_history(
    request: Request,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role("admin"))
):
    # HTMX hx-delete might send params in query or body depending on hx-include behavior
    search = request.query_params.get("search")
    status = request.query_params.get("status")
    
    if search is None or status is None:
        try:
            form = await request.form()
            if search is None: search = form.get("search")
            if status is None: status = form.get("status")
        except:
            pass

    print(f"[Sible] Deleting filtered history: search='{search}', status='{status}'")
    service.delete_all_runs(search=search, status=status)
    response = Response(status_code=200)
    response.headers["HX-Refresh"] = "true"
    return response

@router.delete("/history/run/{run_id}")
async def delete_run(
    run_id: int,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role("admin"))
):
    success = service.delete_run(run_id)
    if success:
        return Response(status_code=200)
    return Response(status_code=404)

@router.get("/history/run/{run_id}")
async def get_run_details(
    run_id: int, 
    request: Request,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
):
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
    runs, total_count = service.get_playbook_runs(name, limit=limit, offset=offset)
    
    import math
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1

    from sqlmodel import select
    from app.models import Host
    from app.dependencies import get_db
    db = next(get_db())
    groups = list(set(h.group_name for h in db.exec(select(Host)).all() if h.group_name))
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
        "groups": groups
    })

@router.delete("/history/playbook/{name:path}/all")
async def delete_playbook_history(
    name: str,
    service: HistoryService = Depends(get_history_service),
    current_user: User = Depends(requires_role("admin"))
):
    service.delete_playbook_runs(name)
    response = Response(status_code=200)
    trigger_toast(response, f"History for {name} cleared", "success")
    response.headers["HX-Refresh"] = "true"
    return response
