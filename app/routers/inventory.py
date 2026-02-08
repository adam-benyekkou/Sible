from fastapi import APIRouter, Request, Response, Depends, Form
from app.templates import templates
from sqlmodel import Session, select
from app.dependencies import get_db, requires_role
from app.models import Host, User
from app.schemas.host import HostCreate, HostUpdate
from app.services.inventory import InventoryService
from app.utils.htmx import trigger_toast
from fastapi.responses import HTMLResponse

router = APIRouter()

# --- Page Routes ---

@router.get("/inventory")
async def get_inventory_page(
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    content = InventoryService.get_inventory_content()
    context = {"request": request, "content": content}
    return templates.TemplateResponse("inventory.html", context)

@router.post("/inventory/save")
async def save_inventory_content(
    request: Request,
    current_user: User = Depends(requires_role(["admin"]))
):
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
):
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
async def list_hosts(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    hosts = db.exec(select(Host)).all()
    return templates.TemplateResponse("partials/inventory_table_rows.html", {
        "request": request,
        "hosts": hosts
    })

@router.post("/api/inventory/hosts")
async def create_host(
    request: Request,
    alias: str = Form(...),
    hostname: str = Form(...),
    ssh_user: str = Form("root"),
    ssh_port: int = Form(22),
    ssh_key_secret: str = Form(None),
    ssh_password_secret: str = Form(None),
    group_name: str = Form("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
):
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
            ssh_password_secret=ssh_password_secret,
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
):
    host = db.get(Host, host_id)
    if not host:
        return Response(status_code=404)
        
    if alias: host.alias = InventoryService.sanitize_ansible_name(alias)
    if hostname: host.hostname = hostname
    if ssh_user: host.ssh_user = ssh_user
    if ssh_port: host.ssh_port = ssh_port
    if group_name: host.group_name = InventoryService.sanitize_group_name(group_name)
    
    # Handle secrets
    form_data = await request.form()
    if 'ssh_key_secret' in form_data: host.ssh_key_secret = form_data.get('ssh_key_secret') or None
    if 'ssh_password_secret' in form_data: host.ssh_password_secret = form_data.get('ssh_password_secret') or None
    
    db.add(host)
    db.commit()
    InventoryService.sync_db_to_ini(db)
    
    response = Response(status_code=200)
    trigger_toast(response, "Host updated", "success")
    response.headers["HX-Trigger"] = "inventory-refresh"
    return response

@router.delete("/api/inventory/hosts/{host_id}")
async def delete_host(
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
):
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
async def get_inventory_secrets(
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
):
    from app.models.settings import EnvVar
    # User asked for secrets dropdown.
    secrets = db.exec(select(EnvVar)).all()
    # return simple list
    return [{"key": s.key, "is_secret": s.is_secret} for s in secrets]

@router.get("/api/inventory/targets")
async def get_inventory_targets(
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

@router.get("/host/{host_id}/card")
async def get_host_card(
    request: Request, 
    host_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
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
async def get_dashboard_stats(db: Session = Depends(get_db)):
    hosts = db.exec(select(Host)).all()
    total = len(hosts)
    online = len([h for h in hosts if h.status == "online"])
    uptime_pct = (online / total * 100) if total > 0 else 0
    
    return {
        "total": total,
        "online": online,
        "uptime_percentage": round(uptime_pct, 1)
    }
