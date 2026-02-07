from fastapi import APIRouter, Request, Response, Form, File, UploadFile, Depends
from fastapi.responses import HTMLResponse
from typing import Optional
from app.templates import templates
from app.core.config import get_settings
from app.dependencies import get_settings_service, get_playbook_service, get_notification_service, get_db, requires_role, get_current_user
from app.services import SettingsService, PlaybookService, NotificationService, InventoryService
from app.utils.htmx import trigger_toast
from app.core.hashing import get_password_hash
from app.models import PlaybookConfig, User
import shutil
from sqlmodel import Session, select
import json

settings_conf = get_settings()
router = APIRouter()

# Helper to render the common settings shell with active tab
async def render_settings_page(request: Request, active_tab: str, context: dict = {}):
    settings = get_settings_conf() # use the loaded config or service
    # We need to make sure we have the basics for the sidebar or common elements
    # Currently layout.html handles most. settings.html handles the sidebar.
    
    full_context = {
        "request": request,
        "active_tab": active_tab, 
        **context
    }
    return templates.TemplateResponse("settings.html", full_context)

def get_settings_conf():
    return get_settings()

@router.get("/settings")
async def get_settings_root(request: Request):
    return RedirectResponse(url="/settings/general")

@router.get("/settings/general")
async def get_settings_general(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    settings = service.get_settings()
    context = {"settings": settings}
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_general.html", {"request": request, **context})
        
    return await render_settings_page(request, "general", context)

@router.get("/settings/secrets")
async def get_settings_secrets(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    env_vars = service.get_env_vars()
    context = {"env_vars": env_vars}

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_secrets.html", {"request": request, **context})

    return await render_settings_page(request, "secrets", context)

@router.get("/settings/inventory")
async def get_settings_inventory(
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    content = InventoryService.get_inventory_content()
    context = {"content": content}

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_inventory.html", {"request": request, **context})

    return await render_settings_page(request, "inventory", context)

@router.get("/settings/users")
async def get_settings_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
):
    # Security: Only admins can access
    users = db.exec(select(User)).all()
    context = {"users": users}

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_users.html", {"request": request, **context})

    return await render_settings_page(request, "users", context)

@router.get("/settings/users/{user_id}/edit")
async def get_user_edit_form(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
):
    user = db.get(User, user_id)
    if not user:
        return Response("User not found", status_code=404)
        
    return templates.TemplateResponse("partials/user_edit_form.html", {
        "request": request, 
        "user": user
    })

@router.get("/settings/retention")
async def get_settings_retention(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    playbook_service: PlaybookService = Depends(get_playbook_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    settings = service.get_settings()
    
    # Get flat list of playbooks from tree
    def flatten_playbooks(items):
        flat = []
        for item in items:
            if item["type"] == "file":
                flat.append(item)
            elif item["type"] == "directory":
                flat.extend(flatten_playbooks(item["children"]))
        return flat

    playbooks_tree = playbook_service.list_playbooks()
    all_playbooks = flatten_playbooks(playbooks_tree)
    
    # Get overrides
    configs = {c.playbook_name: c for c in db.exec(select(PlaybookConfig)).all()}
    
    # Prepare data for template
    pb_list = []
    for pb in all_playbooks:
        path = pb["path"]
        conf = configs.get(path)
        pb_list.append({
            "name": path,
            "retention": conf.retention_days if conf else None,
            "max_runs": conf.max_runs if conf else None
        })
        
    context = {
        "global_retention": settings.global_retention_days,
        "global_max_runs": settings.global_max_runs,
        "playbooks": pb_list
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_retention.html", {"request": request, **context})

    return await render_settings_page(request, "retention", context)

@router.get("/settings/notifications")
async def get_settings_notifications(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    settings = service.get_settings()
    context = {"settings": settings}
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_notifications.html", {"request": request, **context})

    return await render_settings_page(request, "notifications", context)

@router.post("/settings/general")
async def save_settings_general(
    request: Request,
    app_name: str = Form(...),
    auth_enabled: str = Form(None),
    auth_username: str = Form("admin"),
    auth_password: str = Form(None),
    logo: UploadFile = File(None),
    favicon: UploadFile = File(None),
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    update_data = {
        "app_name": app_name,
        "auth_enabled": auth_enabled == "on",
        "auth_username": auth_username
    }
    
    if auth_password and auth_password.strip():
        update_data["auth_password"] = get_password_hash(auth_password)
    
    upload_dir = settings_conf.STATIC_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    if logo and logo.filename:
        logo_path = f"/static/uploads/{logo.filename}"
        with open(settings_conf.BASE_DIR / logo_path.lstrip("/"), "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        update_data["logo_path"] = logo_path
        
    if favicon and favicon.filename:
        fav_path = f"/static/uploads/{favicon.filename}"
        with open(settings_conf.BASE_DIR / fav_path.lstrip("/"), "wb") as buffer:
            shutil.copyfileobj(favicon.file, buffer)
        update_data["favicon_path"] = fav_path
        
    service.update_settings(update_data)
    
    response = Response(status_code=200)
    trigger_toast(response, "Settings updated", "success")
    return response

@router.get("/settings/secrets")
async def get_settings_secrets(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    env_vars = service.get_env_vars()
    return templates.TemplateResponse("partials/settings_secrets.html", {
        "request": request,
        "env_vars": env_vars
    })

@router.post("/settings/secrets")
async def create_env_var(
    request: Request, 
    key: str = Form(...), 
    value: str = Form(...), 
    is_secret: str = Form(None),
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    service.create_env_var(key, value, is_secret == "on")
    response = Response(status_code=200)
    trigger_toast(response, f"Variable '{key}' added", "success")
    response.headers["HX-Trigger-After"] = "secrets-refresh"
    return response

@router.delete("/settings/secrets/{env_id}")
async def delete_env_var(
    env_id: int,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    key = service.delete_env_var(env_id)
    if key:
        response = Response(status_code=200)
        trigger_toast(response, f"Variable '{key}' deleted", "success")
        return response
    return Response(status_code=404)

@router.get("/partials/settings/secrets/edit/{env_id}")
async def get_settings_secrets_edit(
    request: Request, 
    env_id: int,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    env_var = service.get_env_var(env_id)
    if not env_var:
        return Response(status_code=404)
    return templates.TemplateResponse("partials/secrets_edit_row.html", {
        "request": request,
        "var": env_var
    })

@router.post("/settings/secrets/{env_id}")
async def update_env_var(
    request: Request, 
    env_id: int, 
    key: str = Form(...), 
    value: str = Form(""), 
    is_secret: str = Form(None),
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    env_var = service.update_env_var(env_id, key, value, is_secret == "on")
    if not env_var:
        return Response("Secret not found", status_code=404)
    
    response = templates.TemplateResponse("partials/secrets_row.html", {
        "request": request,
        "var": env_var
    })
    trigger_toast(response, f"Variable '{key}' updated", "success")
    return response

@router.get("/partials/settings/secrets/list")
async def get_secrets_list(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    env_vars = service.get_env_vars()
    return templates.TemplateResponse("partials/secrets_list.html", {
        "request": request,
        "env_vars": env_vars
    })



@router.post("/settings/inventory")
async def save_settings_inventory(
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
    
    response = Response(status_code=200)
    trigger_toast(response, "Inventory saved", "success")
    return response

@router.post("/settings/inventory/ping")
async def ping_inventory(
    request: Request,
    current_user: User = Depends(requires_role(["admin"]))
):
    output = await InventoryService.ping_all()
    return f'<pre class="log-output" style="max-height: 300px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px;">{output}</pre>'

@router.get("/settings/retention_tab")
async def get_settings_retention_tab(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    playbook_service: PlaybookService = Depends(get_playbook_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    settings = service.get_settings()
    
    # Get flat list of playbooks from tree
    def flatten_playbooks(items):
        flat = []
        for item in items:
            if item["type"] == "file":
                flat.append(item)
            elif item["type"] == "directory":
                flat.extend(flatten_playbooks(item["children"]))
        return flat

    playbooks_tree = playbook_service.list_playbooks()
    all_playbooks = flatten_playbooks(playbooks_tree)
    
    # Get overrides
    configs = {c.playbook_name: c for c in db.exec(select(PlaybookConfig)).all()}
    
    # Prepare data for template
    pb_list = []
    for pb in all_playbooks:
        path = pb["path"]
        conf = configs.get(path)
        pb_list.append({
            "name": path,
            "retention": conf.retention_days if conf else None,
            "max_runs": conf.max_runs if conf else None
        })
        
    return templates.TemplateResponse("partials/settings_retention.html", {
        "request": request,
        "global_retention": settings.global_retention_days,
        "global_max_runs": settings.global_max_runs,
        "playbooks": pb_list
    })

@router.post("/settings/retention")
async def save_retention_settings(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
):
    form = await request.form()
    global_retention = form.get("global_retention")
    global_max_runs = form.get("global_max_runs")
    
    update_data = {}
    if global_retention: update_data["global_retention_days"] = int(global_retention)
    if global_max_runs: update_data["global_max_runs"] = int(global_max_runs)
    if update_data: service.update_settings(update_data)
    
    overrides = {}
    for key, value in form.items():
        if key.startswith("retention_"):
            name = key.replace("retention_", "")
            if name not in overrides: overrides[name] = {}
            overrides[name]['retention'] = value
        elif key.startswith("max_runs_"):
            name = key.replace("max_runs_", "")
            if name not in overrides: overrides[name] = {}
            overrides[name]['max_runs'] = value
            
    for pb_name, values in overrides.items():
        retention_val = values.get('retention')
        max_runs_val = values.get('max_runs')
        p_conf = db.get(PlaybookConfig, pb_name)
        if (retention_val and retention_val.strip()) or (max_runs_val and max_runs_val.strip()):
            if not p_conf: p_conf = PlaybookConfig(playbook_name=pb_name)
            if retention_val and retention_val.strip(): p_conf.retention_days = int(retention_val)
            if max_runs_val and max_runs_val.strip(): p_conf.max_runs = int(max_runs_val)
            else: p_conf.max_runs = None
            db.add(p_conf)
        else:
                if p_conf: db.delete(p_conf)
    db.commit()
    
    response = Response(status_code=200)
    trigger_toast(response, "Retention settings saved", "success")
    return response

@router.get("/settings/notifications")
async def get_settings_notifications(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    settings = service.get_settings()
    return templates.TemplateResponse("partials/settings_notifications.html", {
        "request": request,
        "settings": settings
    })

@router.post("/settings/notifications")
async def save_notification_settings(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    form = await request.form()
    apprise_url = form.get("apprise_url")
    notify_on_success = form.get("notify_on_success") == "on"
    notify_on_failure = form.get("notify_on_failure") == "on"
    
    service.update_settings({
        "apprise_url": apprise_url,
        "notify_on_success": notify_on_success,
        "notify_on_failure": notify_on_failure
    })
    
    response = Response(status_code=200)
    trigger_toast(response, "Notification settings saved", "success")
    return response

@router.post("/settings/test-notification")
async def test_notification(
    request: Request,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(requires_role(["admin"]))
):
    try:
        service.send_notification("This is a test notification from Sible!", title="Sible Test")
        response = Response(status_code=200)
        trigger_toast(response, "Test notification sent!", "success")
    except Exception as e:
        response = Response(status_code=200)
        trigger_toast(response, f"Failed to send: {str(e)}", "error")
    return response
@router.get("/gitops", response_class=HTMLResponse)
async def settings_gitops_page(request: Request, user: dict = Depends(get_current_user)):
    requires_role("admin")(user)
    return await render_settings_page(request, "gitops")

@router.post("/api/settings/gitops")
async def update_gitops_settings(
    request: Request,
    git_repository_url: Optional[str] = Form(None),
    git_ssh_key: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    settings_service: SettingsService = Depends(get_settings_service)
):
    requires_role("admin")(user)
    
    # Clean up key line endings if present
    if git_ssh_key:
        git_ssh_key = git_ssh_key.replace("\r\n", "\n").strip()
        
    try:
        settings_service.update_settings({
            "git_repository_url": git_repository_url,
            "git_ssh_key": git_ssh_key
        })
        
        return trigger_toast(Response(), "GitOps configuration saved.", "success")
    except Exception as e:
        return trigger_toast(Response(), f"Error saving settings: {e}", "error")
