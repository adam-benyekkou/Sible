from fastapi import APIRouter, Request, Response, Form, File, UploadFile, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, Any, List
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
from app.utils.path import validate_path

settings_conf = get_settings()
router = APIRouter()

# Helper to render the common settings shell with active tab
async def render_settings_page(request: Request, active_tab: str, context: dict[str, Any] = {}) -> Response:
    """Helper to render the common settings shell with active tab.

    Args:
        request: FastAPI request.
        active_tab: ID for the active sidebar navigation item.
        context: Additional data for the child templates.

    Returns:
        TemplateResponse for the settings layout.
    """
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
async def get_settings_root(request: Request) -> RedirectResponse:
    """Redirects the root /settings path to general settings.

    Args:
        request: FastAPI request.

    Returns:
        307 Temporary Redirect to /settings/general.
    """
    return RedirectResponse(url="/settings/general")

@router.get("/settings/general")
async def get_settings_general(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Renders the general configuration page (App name, Auth, Paths).

    Args:
        request: Request object.
        service: Injected settings service.
        current_user: Admin access required.

    Returns:
        TemplateResponse for general settings.
    """
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
) -> Response:
    """Renders the environment variables and secrets management page.

    Args:
        request: Request object.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        TemplateResponse for secrets management (full or partial).
    """
    env_vars = service.get_env_vars()
    context = {"env_vars": env_vars}

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_secrets.html", {"request": request, **context})

    return await render_settings_page(request, "secrets", context)



@router.get("/settings/users")
async def get_settings_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role("admin"))
) -> Response:
    """Renders the user management table.

    Args:
        request: Request object.
        db: Database session.
        current_user: Admin access required.

    Returns:
        TemplateResponse for user management.
    """
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
) -> Response:
    """Returns the edit form for a specific user in a modal.

    Args:
        request: Request object.
        user_id: Target user PK.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Form partial template.
    """
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
) -> Response:
    """Renders the log retention and cleanup policy page.

    Why: Sible supports both global and per-playbook retention rules.
    This page aggregates these policies and allows pinpointing overrides.

    Args:
        request: Request object.
        service: Settings service.
        playbook_service: Playbook service for directory listing.
        db: Database session.
        current_user: Operator or admin.

    Returns:
        TemplateResponse for retention settings.
    """
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
            "retention": conf.retention_days if (conf and conf.retention_days is not None) else None,
            "max_runs": conf.max_runs if (conf and conf.max_runs is not None) else None,
            "notify_on_success": conf.notify_on_success if conf else None,
            "notify_on_failure": conf.notify_on_failure if conf else None
        })
        
    context = {
        "global_retention": settings.global_retention_days,
        "global_max_runs": settings.global_max_runs,
        "playbooks": pb_list
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_retention.html", {"request": request, **context})

    return await render_settings_page(request, "retention", context)

    return await render_settings_page(request, "notifications", context)

@router.post("/settings/general")
async def save_settings_general(
    request: Request,
    app_name: str = Form(...),
    auth_enabled: Optional[str] = Form(None),
    auth_username: str = Form("admin"),
    auth_password: Optional[str] = Form(None),
    timezone: str = Form("UTC"),
    theme: str = Form("light"),
    logo: Optional[UploadFile] = File(None),
    favicon: Optional[UploadFile] = File(None),
    playbooks_path: str = Form("/app/playbooks"),
    service: SettingsService = Depends(get_settings_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Saves general application settings and updates user preferences.

    Why: Handles file uploads for logos/favicons and ensures that the
    application name and auth settings are persistently stored in the DB.

    Args:
        request: Request object.
        app_name: Custom application title.
        auth_enabled: Whether password auth is required.
        auth_username: Default admin username.
        auth_password: New password (if provided).
        timezone: Global display timezone.
        theme: UI theme (light/dark).
        logo: Uploaded logo image.
        favicon: Uploaded favicon image.
        playbooks_path: Physical path to Ansible playbooks.
        service: Settings service.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Response with success toast.
    """
    update_data = {
        "app_name": app_name,
        "auth_enabled": auth_enabled == "on",
        "auth_username": auth_username,
        "playbooks_path": playbooks_path
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
    
    # Save user preferences
    user = db.get(User, current_user.id)
    if user:
        user.timezone = timezone
        user.theme = theme
        db.add(user)
        db.commit()
    
    response = Response(status_code=200)
    trigger_toast(response, "Settings updated", "success")
    return response

@router.post("/settings/validate-path")
async def validate_playbooks_path(
    request: Request,
    playbooks_path: str = Form(...),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Validates if a filesystem path is readable/writable for Sible.

    Args:
        request: Request object.
        playbooks_path: Path string to check.
        current_user: Admin access required.

    Returns:
        HTML fragment with success or error message.
    """
    error = validate_path(playbooks_path)
    if error:
        return HTMLResponse(
            content=f'<div class="text-error text-xs mt-1 flex items-center gap-1"><i data-lucide="alert-circle" class="w-3 h-3"></i> {error}</div>',
            status_code=200
        )
    return HTMLResponse(
        content='<div class="text-success text-xs mt-1 flex items-center gap-1"><i data-lucide="check-circle" class="w-3 h-3"></i> Path is valid and accessible</div>',
        status_code=200
    )

@router.post("/settings/theme")
async def update_theme(
    request: Request,
    theme: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Updates the UI theme preference for the current user.

    Args:
        request: Request object.
        theme: New theme choice.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Response with success toast.
    """
    user = db.get(User, current_user.id)
    if not user:
        return Response(status_code=404)
        
    user.theme = theme
    db.add(user)
    db.commit()
    
    response = Response(status_code=200)
    trigger_toast(response, f"Theme changed to {theme}", "success")
    return response

# REDUNDANT ENDPOINT REMOVED (Handled in @router.get("/settings/secrets") above)

@router.post("/settings/secrets")
async def create_env_var(
    request: Request, 
    key: str = Form(...), 
    value: str = Form(...), 
    is_secret: Optional[str] = Form(None),
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Creates a new environment variable or secret.

    Why: Sible treats all manual variables as secrets (encrypted) by default
    to ensure security during Ansible executions.

    Args:
        request: Request object.
        key: Variable name (e.g., ANSIBLE_SSH_PASS).
        value: Variable value.
        is_secret: (Legacy) Boolean string.
        service: Settings service.
        current_user: Admin access required.

    Returns:
        Empty response with refresh trigger and success toast.
    """
    # Normalize newlines and strip whitespace for secrets
    value = value.replace("\r\n", "\n").strip()
    service.create_env_var(key, value, True)
    response = Response(status_code=200)
    trigger_toast(response, f"Variable '{key}' added", "success")
    response.headers["HX-Trigger-After"] = "secrets-refresh"
    return response

@router.delete("/settings/secrets/{env_id}")
async def delete_env_var(
    env_id: int,
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Deletes an environment variable.

    Args:
        env_id: PK of the variable.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        Success toast or 404.
    """
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
) -> Response:
    """Returns the edit form for a secret in a table row.

    Args:
        request: Request object.
        env_id: variable PK.
        service: Settings service.
        current_user: Admin access required.

    Returns:
        Row fragment for editing.
    """
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
    value: Optional[str] = Form(""), 
    is_secret: Optional[str] = Form(None),
    service: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Updates an existing environment variable.

    Args:
        request: Request object.
        env_id: target PK.
        key: New key name.
        value: New value.
        is_secret: (Legacy).
        service: Settings service.
        current_user: Admin access required.

    Returns:
        Updated table row fragment.
    """
    # Normalize newlines and strip whitespace for secrets
    if value:
        value = value.replace("\r\n", "\n").strip()
    env_var = service.update_env_var(env_id, key, value, True)
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
) -> Response:
    """Returns the partial HTML list of secrets.

    Args:
        request: Request object.
        service: Injected service.
        current_user: Admin access required.

    Returns:
        List fragment.
    """
    env_vars = service.get_env_vars()
    return templates.TemplateResponse("partials/secrets_list.html", {
        "request": request,
        "env_vars": env_vars
    })





# REDUNDANT ENDPOINT REMOVED (Handled in @router.get("/settings/retention") above)

@router.post("/settings/retention")
async def save_retention_settings(
    request: Request,
    service: SettingsService = Depends(get_settings_service),
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Saves global and per-playbook log retention policies.

    Args:
        request: Request containing dynamic form keys for overrides.
        service: Settings service.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Response with success toast.
    """
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
        elif key.startswith("max_runs_"):
            name = key.replace("max_runs_", "")
            if name not in overrides: overrides[name] = {}
            overrides[name]['max_runs'] = value

    # We also need to handle cases where the keys are MISSING
    def flatten_playbooks(items):
        flat = []
        for item in items:
            if item["type"] == "file": flat.append(item["path"])
            elif item["type"] == "directory": flat.extend(flatten_playbooks(item["children"]))
        return flat

    from app.dependencies import get_playbook_service
    ps = get_playbook_service()
    all_pb_names = flatten_playbooks(ps.list_playbooks())

    for pb_name in all_pb_names:
        p_data = overrides.get(pb_name, {})
        retention_val = p_data.get('retention')
        max_runs_val = p_data.get('max_runs')
        
        p_conf = db.get(PlaybookConfig, pb_name)
        
        # We save if ANY field is set (not None/Empty)
        # Note: Retention and Max Runs are strings from the form
        has_retention = retention_val and retention_val.strip()
        has_max_runs = max_runs_val and max_runs_val.strip()
        
        if has_retention or has_max_runs:
            if not p_conf: p_conf = PlaybookConfig(playbook_name=pb_name)
            
            if has_retention: p_conf.retention_days = int(retention_val)
            else: p_conf.retention_days = None
            
            if has_max_runs: p_conf.max_runs = int(max_runs_val)
            else: p_conf.max_runs = None
            
            db.add(p_conf)
        else:
            # If it has notification overrides, we don't delete it here
            # We only delete if it exists AND everything is empty
            if p_conf and not (p_conf.notify_on_success is not None or p_conf.notify_on_failure is not None):
                db.delete(p_conf)
    db.commit()
    
    response = Response(status_code=200)
    trigger_toast(response, "Retention settings saved", "success")
    return response

@router.get("/settings/notifications")
async def get_settings_notifications(
    request: Request,
    db: Session = Depends(get_db),
    service: SettingsService = Depends(get_settings_service),
    ps: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Renders the notifications configuration page.

    Args:
        request: Request object.
        db: Database session.
        service: Settings service.
        ps: Playbook service.
        current_user: Admin access required.

    Returns:
        TemplateResponse for notification settings.
    """
    settings = service.get_settings()
    
    def flatten_playbooks(items):
        flat = []
        for item in items:
            if item["type"] == "file": flat.append(item["path"])
            elif item["type"] == "directory": flat.extend(flatten_playbooks(item["children"]))
        return flat
    
    pb_names = flatten_playbooks(ps.list_playbooks())
    playbooks_data = []
    for name in pb_names:
        config = db.get(PlaybookConfig, name)
        playbooks_data.append({
            "name": name,
            "notify_on_success": config.notify_on_success if config else None,
            "notify_on_failure": config.notify_on_failure if config else None,
        })
    
    context = {
        "settings": settings,
        "playbooks": playbooks_data
    }
    
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/settings_notifications.html", {"request": request, **context})

    return await render_settings_page(request, "notifications", context)

@router.post("/settings/notifications")
async def save_notification_settings(
    request: Request,
    db: Session = Depends(get_db),
    service: SettingsService = Depends(get_settings_service),
    ps: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Saves notification triggers (Apprise) and per-playbook overrides.

    Args:
        request: Request containing dropdown/checkbox states.
        db: Database session.
        service: Settings service.
        ps: Playbook service.
        current_user: Admin access required.

    Returns:
        Response with success toast.
    """
    form = await request.form()
    apprise_url = form.get("apprise_url")
    
    # Global triggers (now dropdowns)
    global_success = form.get("notify_on_success") == "true"
    global_failure = form.get("notify_on_failure") == "true"
    
    service.update_settings({
        "apprise_url": apprise_url,
        "notify_on_success": global_success,
        "notify_on_failure": global_failure
    })
    
    # Per-playbook overrides
    overrides = {}
    for key, value in form.items():
        if key.startswith("notify_success_"):
            name = key.replace("notify_success_", "")
            if name not in overrides: overrides[name] = {}
            val = value.strip()
            overrides[name]['notify_on_success'] = True if val == "true" else False if val == "false" else None
        elif key.startswith("notify_failure_"):
            name = key.replace("notify_failure_", "")
            if name not in overrides: overrides[name] = {}
            val = value.strip()
            overrides[name]['notify_on_failure'] = True if val == "true" else False if val == "false" else None

    # Sync overrides to database
    def flatten_playbooks(items):
        flat = []
        for item in items:
            if item["type"] == "file": flat.append(item["path"])
            elif item["type"] == "directory": flat.extend(flatten_playbooks(item["children"]))
        return flat
        
    all_pb_names = flatten_playbooks(ps.list_playbooks())
    
    for pb_name in all_pb_names:
        p_data = overrides.get(pb_name, {})
        notify_success = p_data.get('notify_on_success')
        notify_failure = p_data.get('notify_on_failure')
        
        p_conf = db.get(PlaybookConfig, pb_name)
        
        # We only care about notification values here
        if notify_success is not None or notify_failure is not None:
            if not p_conf: p_conf = PlaybookConfig(playbook_name=pb_name)
            p_conf.notify_on_success = notify_success
            p_conf.notify_on_failure = notify_failure
            db.add(p_conf)
        else:
            # If notification overrides are gone, but retention exists, don't delete!
            if p_conf:
                p_conf.notify_on_success = None
                p_conf.notify_on_failure = None
                # Only delete if NOTHING is left
                if p_conf.retention_days is None and p_conf.max_runs is None:
                    db.delete(p_conf)
                else:
                    db.add(p_conf)
                    
    db.commit()
    
    response = Response(status_code=200)
    trigger_toast(response, "Notification settings saved", "success")
    return response

@router.post("/settings/test-notification")
async def test_notification(
    request: Request,
    service: NotificationService = Depends(get_notification_service),
    current_user: User = Depends(requires_role(["admin"]))
) -> Response:
    """Triggers a test notification via the configured Apprise URL.

    Args:
        request: Request object.
        service: Notification service.
        current_user: Admin access required.

    Returns:
        Response with success/error toast.
    """
    try:
        service.send_notification("This is a test notification from Sible!", title="Sible Test")
        response = Response(status_code=200)
        trigger_toast(response, "Test notification sent!", "success")
    except Exception as e:
        response = Response(status_code=200)
        trigger_toast(response, f"Failed to send: {str(e)}", "error")
    return response
@router.get("/settings/gitops", response_class=RedirectResponse)
async def settings_gitops_page():
    return RedirectResponse(url="/settings/general", status_code=301)
