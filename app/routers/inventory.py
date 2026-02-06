from fastapi import APIRouter, Request, Response, Depends, Form
from app.templates import templates
from sqlmodel import Session, select
from app.dependencies import get_db
from app.models import Host
from app.schemas.host import HostCreate, HostUpdate
from app.services.inventory import InventoryService
from app.utils.htmx import trigger_toast

router = APIRouter()

@router.get("/api/inventory/hosts")
async def list_hosts(request: Request, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
):
    # Validate connection
    is_valid = await InventoryService.verify_connection(hostname, ssh_user, ssh_port)
    if not is_valid:
        response = Response(status_code=400)
        trigger_toast(response, f"Connection failed to {hostname}", "error")
        return response

    try:
        new_host = Host(
            alias=alias, 
            hostname=hostname, 
            ssh_user=ssh_user, 
            ssh_port=ssh_port,
            ssh_key_secret=ssh_key_secret,
            ssh_password_secret=ssh_password_secret,
            group_name=group_name
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
    db: Session = Depends(get_db)
):
    host = db.get(Host, host_id)
    if not host:
        return Response(status_code=404)
        
    if alias: host.alias = alias
    if hostname: host.hostname = hostname
    if ssh_user: host.ssh_user = ssh_user
    if ssh_port: host.ssh_port = ssh_port
    if group_name: host.group_name = group_name
    
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
async def delete_host(host_id: int, db: Session = Depends(get_db)):
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
async def import_inventory(request: Request, db: Session = Depends(get_db)):
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
async def get_inventory_secrets(db: Session = Depends(get_db)):
    from app.models.settings import EnvVar
    # User asked for secrets dropdown.
    secrets = db.exec(select(EnvVar)).all()
    # return simple list
    return [{"key": s.key, "is_secret": s.is_secret} for s in secrets]
