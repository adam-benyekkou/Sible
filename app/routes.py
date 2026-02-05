from fastapi import APIRouter, Request, Response, Form, status, File, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlmodel import Session, select, desc, delete
import asyncio
import json
import os
import shutil

# Models and Services
from app.database import engine
from app.models import JobRun, GlobalConfig, PlaybookConfig, EnvVar
from app.services import PlaybookService, RunnerService, LinterService, SettingsService, InventoryService, NotificationService
from app.auth import check_auth, verify_password, get_password_hash
from app.tasks import add_playbook_job, list_jobs, remove_job, update_job, get_job_info

# Setup Templates
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

# Helper for Toast Headers
def trigger_toast(response: Response, message: str, level: str = "success"):
    trigger_data = {
        "show-toast": {
            "message": message,
            "level": level
        }
    }
    
    current_trigger = response.headers.get("HX-Trigger")
    if current_trigger:
        try:
            current_dict = json.loads(current_trigger)
            if isinstance(current_dict, dict):
                current_dict.update(trigger_data)
                response.headers["HX-Trigger"] = json.dumps(current_dict)
            else:
                response.headers["HX-Trigger"] = json.dumps(trigger_data)
        except:
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
    else:
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

# --- Secrets Management ---

@router.get("/settings/secrets")
async def get_settings_secrets(request: Request):
    with Session(engine) as session:
        env_vars = session.exec(select(EnvVar)).all()
    return templates.TemplateResponse("partials/settings_secrets.html", {
        "request": request,
        "env_vars": env_vars
    })

@router.post("/settings/secrets")
async def create_env_var(request: Request, key: str = Form(...), value: str = Form(...), is_secret: str = Form(None)):
    with Session(engine) as session:
        env_var = EnvVar(key=key, value=value, is_secret=(is_secret == "on"))
        session.add(env_var)
        session.commit()
    
    response = Response(status_code=200)
    trigger_toast(response, f"Variable '{key}' added", "success")
    response.headers["HX-Trigger-After"] = "secrets-refresh"
    return response

@router.delete("/settings/secrets/{env_id}")
async def delete_env_var(env_id: int):
    with Session(engine) as session:
        env_var = session.get(EnvVar, env_id)
        if env_var:
            key = env_var.key
            session.delete(env_var)
            session.commit()
            response = Response(status_code=200)
            trigger_toast(response, f"Variable '{key}' deleted", "success")
            return response
    return Response(status_code=404)

@router.get("/partials/settings/secrets/edit/{env_id}")
async def get_settings_secrets_edit(request: Request, env_id: int):
    with Session(engine) as session:
        env_var = session.get(EnvVar, env_id)
        if not env_var:
            return Response(status_code=404)
        return templates.TemplateResponse("partials/secrets_edit_row.html", {
            "request": request,
            "var": env_var
        })

@router.post("/settings/secrets/{env_id}")
async def update_env_var(request: Request, env_id: int, key: str = Form(...), value: str = Form(""), is_secret: str = Form(None)):
    with Session(engine) as session:
        env_var = session.get(EnvVar, env_id)
        if not env_var:
            return Response("Secret not found", status_code=404)
        
        env_var.key = key
        if is_secret == "on":
            env_var.is_secret = True
            if value.strip():
                env_var.value = value
        else:
            env_var.is_secret = False
            env_var.value = value
            
        session.add(env_var)
        session.commit()
        session.refresh(env_var)
    
    response = templates.TemplateResponse("partials/secrets_row.html", {
        "request": request,
        "var": env_var
    })
    trigger_toast(response, f"Variable '{key}' updated", "success")
    return response

@router.get("/partials/settings/secrets/list")
async def get_secrets_list(request: Request):
    with Session(engine) as session:
        env_vars = session.exec(select(EnvVar)).all()
    return templates.TemplateResponse("partials/secrets_list.html", {
        "request": request,
        "env_vars": env_vars
    })

# --- Settings & Inventory ---

@router.get("/settings")
async def get_settings_page(request: Request):
    return await get_retention_settings(request, template="settings.html")

@router.get("/settings/general")
async def get_settings_general(request: Request):
    settings = SettingsService.get_settings()
    return templates.TemplateResponse("partials/settings_general.html", {
        "request": request,
        "settings": settings
    })

@router.post("/settings/general")
async def save_settings_general(
    request: Request,
    app_name: str = Form(...),
    auth_enabled: str = Form(None),
    auth_username: str = Form("admin"),
    auth_password: str = Form(None),
    logo: UploadFile = File(None),
    favicon: UploadFile = File(None)
):
    update_data = {
        "app_name": app_name,
        "auth_enabled": auth_enabled == "on",
        "auth_username": auth_username
    }
    
    if auth_password and auth_password.strip():
        update_data["auth_password"] = get_password_hash(auth_password)
    
    upload_dir = BASE_DIR / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    if logo and logo.filename:
        logo_path = f"/static/uploads/{logo.filename}"
        with open(BASE_DIR / logo_path.lstrip("/"), "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        update_data["logo_path"] = logo_path
        
    if favicon and favicon.filename:
        fav_path = f"/static/uploads/{favicon.filename}"
        with open(BASE_DIR / fav_path.lstrip("/"), "wb") as buffer:
            shutil.copyfileobj(favicon.file, buffer)
        update_data["favicon_path"] = fav_path
        
    SettingsService.update_settings(update_data)
    
    response = Response(status_code=200)
    trigger_toast(response, "Settings updated", "success")
    return response

@router.get("/settings/inventory")
async def get_settings_inventory(request: Request):
    content = InventoryService.get_inventory_content()
    return templates.TemplateResponse("partials/settings_inventory.html", {
        "request": request,
        "content": content
    })

@router.post("/settings/inventory")
async def save_settings_inventory(request: Request):
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
async def ping_inventory(request: Request):
    output = await InventoryService.ping_all()
    return f'<pre class="log-output" style="max-height: 300px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 4px;">{output}</pre>'

# --- Retention & Notifications ---

async def get_retention_settings(request: Request, template: str):
    settings = SettingsService.get_settings()
    playbooks = PlaybookService.list_playbooks()
    with Session(engine) as session:
        configs = {c.playbook_name: c for c in session.exec(select(PlaybookConfig)).all()}
    return templates.TemplateResponse(template, {
        "request": request,
        "settings": settings,
        "playbooks": playbooks,
        "overrides": configs,
        "active_tab": "retention"
    })

@router.get("/settings/retention_tab")
async def get_settings_retention_tab(request: Request):
    return await get_retention_settings(request, template="partials/settings_retention.html")

@router.post("/settings/retention")
async def save_retention_settings(request: Request):
    form = await request.form()
    global_retention = form.get("global_retention")
    global_max_runs = form.get("global_max_runs")
    
    update_data = {}
    if global_retention: update_data["global_retention_days"] = int(global_retention)
    if global_max_runs: update_data["global_max_runs"] = int(global_max_runs)
    if update_data: SettingsService.update_settings(update_data)
    
    with Session(engine) as session:
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
            p_conf = session.get(PlaybookConfig, pb_name)
            if (retention_val and retention_val.strip()) or (max_runs_val and max_runs_val.strip()):
                if not p_conf: p_conf = PlaybookConfig(playbook_name=pb_name)
                if retention_val and retention_val.strip(): p_conf.retention_days = int(retention_val)
                if max_runs_val and max_runs_val.strip(): p_conf.max_runs = int(max_runs_val)
                else: p_conf.max_runs = None
                session.add(p_conf)
            else:
                 if p_conf: session.delete(p_conf)
        session.commit()
        
    response = Response(status_code=200)
    trigger_toast(response, "Retention settings saved", "success")
    return response

@router.get("/settings/notifications")
async def get_settings_notifications(request: Request):
    settings = SettingsService.get_settings()
    return templates.TemplateResponse("partials/settings_notifications.html", {
        "request": request,
        "settings": settings
    })

@router.post("/settings/notifications")
async def save_notification_settings(request: Request):
    form = await request.form()
    apprise_url = form.get("apprise_url")
    notify_on_success = form.get("notify_on_success") == "on"
    notify_on_failure = form.get("notify_on_failure") == "on"
    
    SettingsService.update_settings({
        "apprise_url": apprise_url,
        "notify_on_success": notify_on_success,
        "notify_on_failure": notify_on_failure
    })
    
    response = Response(status_code=200)
    trigger_toast(response, "Notification settings saved", "success")
    return response

@router.post("/settings/test-notification")
async def test_notification(request: Request):
    try:
        NotificationService.send_notification("This is a test notification from Sible! 🚀", title="Sible Test")
        response = Response(status_code=200)
        trigger_toast(response, "Test notification sent!", "success")
    except Exception as e:
        response = Response(status_code=200)
        trigger_toast(response, f"Failed to send: {str(e)}", "error")
    return response

# --- Core App Routes ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "app_name": "Sible"})

@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    settings = SettingsService.get_settings()
    if settings.auth_enabled and username == settings.auth_username and verify_password(password, settings.auth_password):
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "app_name": "Sible", "error": "Invalid login"})

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/partials/sidebar")
async def get_sidebar(request: Request):
    playbooks = PlaybookService.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {"request": request, "playbooks": playbooks})

@router.get("/playbook/{name:path}")
async def get_playbook_view(name: str, request: Request):
    content = PlaybookService.get_playbook_content(name)
    if content is None:
        return Response(content="<p>File not found</p>", media_type="text/html")
    return templates.TemplateResponse("partials/editor.html", {
        "request": request, 
        "name": name, 
        "content": content,
        "has_requirements": PlaybookService.has_requirements(name)
    })

@router.post("/playbook/{name:path}")
async def save_playbook(name: str, request: Request):
    form = await request.form()
    content = form.get("content")
    if content is None:
        response = Response(status_code=200)
        trigger_toast(response, "Missing content", "error")
        return response
    
    success = PlaybookService.save_playbook_content(name, content)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to save file", "error")
        return response
    
    response = Response("Saved successfully")
    trigger_toast(response, "Playbook saved", "success")
    return response

@router.post("/playbook")
async def create_playbook(request: Request):
    name = request.headers.get("HX-Prompt")
    if not name:
        response = Response(status_code=200)
        trigger_toast(response, "Playbook name is required", "error")
        return response
    
    success = PlaybookService.create_playbook(name)
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
async def delete_playbook(name: str):
    success = PlaybookService.delete_playbook(name)
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
async def stop_playbook_endpoint(name: str):
    success = RunnerService.stop_playbook(name)
    if success:
        response = Response(status_code=200)
        trigger_toast(response, "Stopping playbook...", "info")
        return response
    response = Response(status_code=200)
    trigger_toast(response, "Process not found or already stopped", "error")
    return response

@router.get("/stream/{name:path}")
async def stream_playbook_endpoint(name: str, mode: str = "run"):
    check_mode = (mode == "check")
    async def event_generator():
        yield "event: start\ndata: Connected\n\n"
        if mode == "galaxy":
             async for line in RunnerService.install_requirements(name):
                yield f"data: {line}\n\n"
        else:
            async for line in RunnerService.run_playbook(name, check_mode=check_mode):
                yield f"data: {line}\n\n"
        yield "event: end\ndata: Execution finished\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/queue")
async def get_queue_view(request: Request):
    jobs = list_jobs()
    return templates.TemplateResponse("queue.html", {"request": request, "jobs": jobs, "active_tab": "queue"})

@router.post("/schedule")
async def create_schedule(playbook: str = Form(...), cron: str = Form(...)):
    job_id = add_playbook_job(playbook, cron)
    response = Response(status_code=200)
    if job_id:
        trigger_toast(response, f"Scheduled {playbook}", "success")
    else:
        trigger_toast(response, "Invalid Cron Expression", "error")
    return response

@router.delete("/schedule/{job_id}")
async def delete_schedule(job_id: str):
    success = remove_job(job_id)
    response = Response(status_code=200)
    if success:
        trigger_toast(response, "Schedule removed", "success")
    else:
        trigger_toast(response, "Failed to remove", "error")
    return response

@router.put("/schedule/{job_id}")
async def update_schedule(job_id: str, request: Request, cron: str = Form(...)):
    success = update_job(job_id, cron)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed: Invalid Cron", "error")
        return response
    job = get_job_info(job_id)
    response = templates.TemplateResponse("partials/queue_row.html", {"request": request, "job": job})
    trigger_toast(response, "Schedule updated", "success")
    return response

@router.get("/partials/queue/row/{job_id}")
async def get_job_row(job_id: str, request: Request):
    job = get_job_info(job_id)
    if not job: return Response("")
    return templates.TemplateResponse("partials/queue_row.html", {"request": request, "job": job})

@router.get("/history")
async def get_history_page(request: Request):
    with Session(engine) as session:
        runs = session.exec(select(JobRun).order_by(desc(JobRun.start_time)).limit(50)).all()
    return templates.TemplateResponse("history.html", {"request": request, "runs": runs, "active_tab": "history"})

@router.delete("/history/all")
async def delete_all_history():
    with Session(engine) as session:
        session.exec(delete(JobRun))
        session.commit()
    response = Response(status_code=200)
    response.headers["HX-Refresh"] = "true"
    return response

@router.delete("/history/run/{run_id}")
async def delete_run(run_id: int):
    with Session(engine) as session:
        run = session.get(JobRun, run_id)
        if run:
            session.delete(run)
            session.commit()
            return Response(status_code=200)
        return Response(status_code=404)

@router.get("/history/run/{run_id}")
async def get_run_details(run_id: int, request: Request):
    with Session(engine) as session:
        run = session.get(JobRun, run_id)
    if not run: return Response("Run not found", status_code=404)
    return templates.TemplateResponse("partials/log_viewer_modal.html", {"request": request, "run": run})

@router.post("/lint")
async def lint_playbook(request: Request):
    form = await request.form()
    content = form.get("content")
    if not content: return []
    return await LinterService.lint_playbook_content(content)

def get_global_app_name():
    try: return SettingsService.get_settings().app_name
    except: return "Sible"

templates.env.globals["app_name"] = get_global_app_name
templates.env.globals["get_settings"] = SettingsService.get_settings
