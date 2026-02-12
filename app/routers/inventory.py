from fastapi import APIRouter, Request, Response, Depends, Form
from app.templates import templates
from sqlmodel import Session, select
from app.dependencies import get_db, requires_role
from app.models import Host, User, FavoriteServer
from app.schemas.host import HostCreate, HostUpdate
from app.services.inventory import InventoryService
from app.utils.htmx import trigger_toast
from fastapi.responses import HTMLResponse

router = APIRouter()

# --- Page Routes ---

@router.get("/inventory", response_class=HTMLResponse)
def get_inventory_page(
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Renders the main inventory management page.

    Args:
        request: FastAPI request object.
        current_user: Authenticated user with at least watcher role.

    Returns:
        TemplateResponse for the inventory page.
    """
    content = InventoryService.get_inventory_content()
    context = {"request": request, "content": content}
    return templates.TemplateResponse("inventory.html", context)

@router.post("/inventory/save")
async def save_inventory_content(
    request: Request,
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Saves raw INI content from the editor to the physical inventory file.

    Why: Allows power users to bulk-edit the inventory bypassing the DB UI,
    which is then synced back to the DB via a client-side HTMX trigger.

    Args:
        request: Request containing form data 'content'.
        current_user: Admin access required for direct file edits.

    Returns:
        Response with a toast notification trigger.
    """
    form = await request.form()
    content = form.get("content")
    if content is None:
        response = Response(status_code=200)
        trigger_toast(response, "Missing content", "error")
        return response
    
    success = InventoryService.save_inventory_content(content)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to save inventory", "error")
        return response
    
    # After saving raw content, we should also try to import it to DB to keep sync
    # But the UI triggers 'inventory-refresh' via HTMX usually.
    # The existing logic had a separate import call or client-side trigger.
    # We'll follow the pattern: return success, and let client trigger import if needed 
    # OR we can just do it here if checking the previous template logic:
    # hx-on::after-request="if(event.detail.successful) htmx.ajax('POST', '/api/inventory/import', {swap:'none'})"
    # So the client handles the secondary import call. We just return success here.
    
    response = Response(status_code=200)
    trigger_toast(response, "Inventory saved", "success")
    return response

@router.post("/inventory/ping")
async def ping_inventory(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Triggers an Ansible ping across all inventory hosts.

    Why: Refreshes the database 'status' field for all hosts and provides
    the raw Ansible CLI output for debugging connectivity issues.

    Args:
        request: FastAPI request.
        db: Database session.
        current_user: Admin access required.

    Returns:
        HTMLResponse containing the formatted CLI output and a table refresh trigger.
    """
    # Perform status refresh (updates DB)
    await InventoryService.refresh_all_statuses(db)
    
    # Also get the raw ansible ping output if we still want to show it?
    # Actually, the user wants status column in inventory.
    # We can still return the ansible ping output as a log for detail.
    output = await InventoryService.ping_all()
    
    response = HTMLResponse(content=f'<pre class="log-output" style="max-height: 300px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px;">{output}</pre>')
    trigger_toast(response, "Ping check complete", "success")
    response.headers["HX-Trigger"] = "inventory-refresh"
    return response

# --- API Routes ---

@router.get("/api/inventory/hosts")
def list_hosts(
    request: Request, 
    page: int = 1,
    search: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Returns a paginated HTML table of hosts.

    Why: Provides a searchable, paginated view of infrastructure components
    optimized for HTMX partial updates.

    Args:
        request: Request object.
        page: Current page number.
        search: Optional fuzzy filter for alias/hostname.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        TemplateResponse for the table rows partial.
    """
    hosts, total_count = InventoryService.get_hosts_paginated(db, page=page, search=search)
    
    # Get user favorites
    fav_ids = set()
    if current_user:
        favs = db.exec(select(FavoriteServer).where(FavoriteServer.user_id == current_user.id)).all()
        fav_ids = {f.host_id for f in favs}
    
    import math
    limit = 20
    total_pages = math.ceil(total_count / limit)
    has_next = page < total_pages
    has_prev = page > 1
    
    return templates.TemplateResponse("partials/inventory_table_rows.html", {
        "request": request,
        "hosts": hosts,
        "page": page,
        "search": search,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_prev": has_prev,
        "total_count": total_count,
        "fav_ids": fav_ids
    })

@router.post("/api/inventory/hosts/{host_id}/favorite")
def toggle_favorite_host(
    host_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Toggles a host as a 'favorite' for the current user.

    Args:
        host_id: Target host ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Response with success toast and refresh trigger.
    """
    existing = db.exec(
        select(FavoriteServer).where(
            FavoriteServer.user_id == current_user.id,
            FavoriteServer.host_id == host_id
        )
    ).first()
    
    if existing:
        db.delete(existing)
        db.commit()
        response = Response(status_code=200)
        trigger_toast(response, "Removed from favorites", "success")
    else:
        fav = FavoriteServer(user_id=current_user.id, host_id=host_id)
        db.add(fav)
        db.commit()
        response = Response(status_code=200)
        trigger_toast(response, "Added to favorites", "success")
    
    response.headers["HX-Trigger"] = "inventory-refresh"
    return response

@router.post("/api/inventory/hosts")
async def create_host(
    request: Request,
    alias: str = Form(...),
    hostname: str = Form(...),
    ssh_user: str = Form("root"),
    ssh_port: int = Form(22),
    ssh_key_secret: str = Form(None),
    group_name: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Adds a new host to the database and syncs it to the Ansible inventory.

    Why: Sible enforces sanitization of names to ensure Ansible CLI
    compatibility when the DB is exported to INI format.

    Args:
        request: Request object.
        alias: Human-readable name (sanitized for Ansible).
        hostname: SSH destination.
        ssh_user: SSH username.
        ssh_port: SSH port.
        ssh_key_secret: Reference to an EnvVar secret.
        group_name: Ansible group assignment.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Response with status and refresh trigger.
    """
    # Validating connection is good, but blocking creation is bad UX.
    # We will just create it and let the status check handle it later.
    # is_valid = await InventoryService.verify_connection(hostname, ssh_user, ssh_port)

    try:
        new_host = Host(
            alias=InventoryService.sanitize_ansible_name(alias), 
            hostname=hostname, 
            ssh_user=ssh_user, 
            ssh_port=ssh_port,
            ssh_key_secret=ssh_key_secret,
            group_name=InventoryService.sanitize_ansible_name(group_name)
        )
        db.add(new_host)
        db.commit()
        db.refresh(new_host)
        
        # Sync to INI
        InventoryService.sync_db_to_ini(db)
        
        response = Response(status_code=200)
        trigger_toast(response, "Host added", "success")
        # Trigger client-side refresh of the table
        response.headers["HX-Trigger"] = "inventory-refresh"
        return response
    except Exception as e:
        response = Response(status_code=500)
        trigger_toast(response, f"Error: {str(e)}", "error")
        return response

@router.put("/api/inventory/hosts/{host_id}")
async def update_host(
    request: Request,
    host_id: int,
    alias: str = Form(None),
    hostname: str = Form(None),
    ssh_user: str = Form(None),
    ssh_port: int = Form(None),
    group_name: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Updates an existing host record and triggers a filesystem sync.

    Args:
        request: Request containing potential multipart form data.
        host_id: Target host ID.
        alias: New alias.
        hostname: New destination.
        ssh_user: New user.
        ssh_port: New port.
        group_name: New group.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Response with success notification.
    """
    host = db.get(Host, host_id)
    if not host:
        return Response(status_code=404)
        
    if alias: host.alias = InventoryService.sanitize_ansible_name(alias)
    if hostname: host.hostname = hostname
    if ssh_user: host.ssh_user = ssh_user
    if ssh_port: host.ssh_port = ssh_port
    if group_name: host.group_name = InventoryService.sanitize_ansible_name(group_name)
    
    # Handle secrets
    form_data = await request.form()
    if 'ssh_key_secret' in form_data: host.ssh_key_secret = form_data.get('ssh_key_secret') or None
    
    db.add(host)
    db.commit()
    InventoryService.sync_db_to_ini(db)
    
    response = Response(status_code=200)
    trigger_toast(response, "Host updated", "success")
    response.headers["HX-Trigger"] = "inventory-refresh"
    return response

@router.delete("/api/inventory/hosts/{host_id}")
def delete_host(
    host_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
):
    host = db.get(Host, host_id)
    if not host:
        return Response(status_code=404)
    
    db.delete(host)
    db.commit()
    InventoryService.sync_db_to_ini(db)
    
    response = Response(status_code=200)
    trigger_toast(response, "Host deleted", "success")
    response.headers["HX-Trigger"] = "inventory-refresh"
    return response

@router.post("/api/inventory/import")
async def import_inventory(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Synchronizes host records in the database with the physical INI file.

    Why: Allows "File-first" workflows where users edit files directly
    on disk and want the UI to reflect those changes.

    Args:
        request: FastAPI request.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Response indicating import result.
    """
    """
    Called when 'Save' is clicked in the raw editor to update DB from File.
    """
    success = InventoryService.import_ini_to_db(db)
    response = Response(status_code=200)
    if success:
        trigger_toast(response, "Inventory imported to DB", "success")
        response.headers["HX-Trigger"] = "inventory-refresh"
    else:
        trigger_toast(response, "Import failed", "error")
    return response

@router.get("/api/inventory/secrets")
def get_inventory_secrets(
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
):
    from app.models.settings import EnvVar
    # User asked for secrets dropdown.
    secrets = db.exec(select(EnvVar)).all()
    # return simple list
    return [{"key": s.key, "is_secret": s.is_secret} for s in secrets]

@router.get("/api/inventory/targets")
def get_inventory_targets(
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    """
    Returns a list of all hosts and groups for selection in the UI.
    """
    hosts = db.exec(select(Host)).all()
    groups = sorted(list(set(h.group_name for h in hosts if h.group_name)))
    
    return {
        "hosts": [{"alias": h.alias, "hostname": h.hostname, "group": h.group_name} for h in hosts],
        "groups": groups,
        "all": ["all"]
    }

@router.get("/api/inventory/targets/picker")
def get_inventory_targets_picker(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    """
    Returns the filtered list of targets for the picker component.
    """
    hosts = db.exec(select(Host)).all()
    q = q.lower()
    
    filtered_hosts = [h for h in hosts if q in h.alias.lower() or q in h.hostname.lower()]
    all_groups = sorted(list(set(h.group_name for h in hosts if h.group_name)))
    filtered_groups = [g for g in all_groups if q in g.lower()]
    
    show_all = q in "all hosts" or not q

    return templates.TemplateResponse("partials/target_picker_list.html", {
        "request": request,
        "hosts": filtered_hosts,
        "groups": filtered_groups,
        "show_all": show_all
    })

@router.get("/api/inventory/host/{host_id}/card")
def get_host_card(
    request: Request, 
    host_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
) -> Response:
    """Renders a detailed information card for a specific host.

    Args:
        request: Request object.
        host_id: Host ID.
        db: Database session.
        current_user: Authenticated operator+.

    Returns:
        TemplateResponse for the server card component.
    """
    from app.models.host import Host
    host = db.get(Host, host_id)
    if not host:
        return Response(status_code=404)
    
    # Render with component
    from app.routers.core import templates
    return templates.TemplateResponse("components/server_card.html", {
        "request": request,
        "host": host
    })

@router.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    hosts = db.exec(select(Host)).all()
    total = len(hosts)
    online = len([h for h in hosts if h.status == "online"])
    uptime_pct = (online / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "online": online,
        "uptime_percentage": round(uptime_pct, 1)
    }
