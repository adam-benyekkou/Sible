from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.services import PlaybookService, RunnerService, LinterService
from app.tasks import add_playbook_job, list_jobs, remove_job, update_job, get_job_info
from app.database import engine
from app.models import JobRun, GlobalConfig, PlaybookConfig
from sqlmodel import Session, select, desc
import asyncio

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/partials/sidebar")
async def get_sidebar(request: Request):
    playbooks = PlaybookService.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {"request": request, "playbooks": playbooks})

@router.get("/playbook/{name}")
async def get_playbook_view(name: str, request: Request):
    content = PlaybookService.get_playbook_content(name)
    if content is None:
        return Response(content="<p>File not found</p>", media_type="text/html")
    
    return templates.TemplateResponse("partials/editor.html", {
        "request": request, 
        "name": name, 
        "content": content
    })

import json

# Helper for Toast Headers
def trigger_toast(response: Response, message: str, level: str = "success"):
    trigger_data = {
        "show-toast": {
            "message": message,
            "level": level
        }
    }
    # If a trigger already exists, we might need to merge, but for now we assume single trigger or append
    # But FastAPI headers are case-insensitive dicts.
    # To be safe with multiple triggers (like refresh + toast), we can merge them if needed.
    # Here we'll just handle sidebar-refresh manually in the same dict if needed.
    
    current_trigger = response.headers.get("HX-Trigger")
    if current_trigger:
        try:
            # If it's already JSON
            current_dict = json.loads(current_trigger)
            current_dict.update(trigger_data)
            response.headers["HX-Trigger"] = json.dumps(current_dict)
        except:
            # If it's a simple string (like "sidebar-refresh")
            trigger_data[current_trigger] = True
            response.headers["HX-Trigger"] = json.dumps(trigger_data)
    else:
        response.headers["HX-Trigger"] = json.dumps(trigger_data)

@router.post("/playbook/{name}")
async def save_playbook(name: str, request: Request):
    form = await request.form()
    content = form.get("content")
    if content is None:
        response = Response(status_code=200) # Use 200 so HTMX processes headers
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
    # Trigger refresh AND toast
    response.headers["HX-Trigger"] = json.dumps({
        "sidebar-refresh": True,
        "show-toast": {
            "message": f"Playbook '{name}' created", 
            "level": "success"
        }
    })
    return response

@router.delete("/playbook/{name}")
async def delete_playbook(name: str):
    success = PlaybookService.delete_playbook(name)
    if not success:
        response = Response(status_code=200)
        trigger_toast(response, "Failed to delete playbook", "error")
        return response
    
    content = """
    <div id="main-content" class="container text-center flex-center h-100" style="color: #868e96;">
        <p>Select a playbook to get started</p>
    </div>
    """
    response = Response(content=content, media_type="text/html")
    response.headers["HX-Trigger"] = json.dumps({
        "sidebar-refresh": True,
        "show-toast": {
            "message": f"Playbook '{name}' deleted", 
            "level": "success"
        }
    })
    return response
@router.post("/run/{name}")
async def run_playbook_endpoint(name: str, request: Request):
    """
    Triggers the playbook execution on the frontend.
    Instead of running it here, we return HTML that connects to the SSE stream.
    """
    # We return the "Running..." state UI which includes the hx-ext="sse" connection
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "run"
    })

@router.post("/check/{name}")
async def check_playbook_endpoint(name: str, request: Request):
    """
    Triggers the playbook Dry Run (Check Mode).
    """
    return templates.TemplateResponse("partials/terminal_connect.html", {
        "request": request,
        "name": name,
        "mode": "check"
    })

@router.get("/stream/{name}")
async def stream_playbook_endpoint(name: str, mode: str = "run"):
    """
    SSE Endpoint.
    """
    check_mode = (mode == "check")
    
    async def event_generator():
        yield "event: start\ndata: Connected to stream\n\n"
        # Pass check_mode to the runner
        async for line in RunnerService.run_playbook(name, check_mode=check_mode):
            # Server-Sent Events format: "data: <payload>\n\n"
            yield f"data: {line}\n\n"
        yield "event: end\ndata: Execution finished\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/queue")
async def get_queue_view(request: Request):
    jobs = list_jobs()
    return templates.TemplateResponse("queue.html", {"request": request, "jobs": jobs, "active_tab": "queue"})

@router.post("/schedule")
async def create_schedule(playbook: str = Form(...), cron: str = Form(...)):
    if not playbook or not cron:
        response = Response(status_code=200)
        trigger_toast(response, "Missing playbook or cron", "error")
        return response
        
    job_id = add_playbook_job(playbook, cron)

    response = Response(status_code=200)
    if job_id:
        trigger_toast(response, f"Scheduled {playbook}", "success")
    else:
        # If job_id is None, it means validation failed (or add failed)
        trigger_toast(response, "Invalid Cron Expression. Format: * * * * *", "error")
    
    return response

@router.delete("/schedule/{job_id}")
async def delete_schedule(job_id: str):
    success = remove_job(job_id)
    response = Response(status_code=200)
    
    if success:
        trigger_toast(response, "Schedule removed", "success")
        # Return empty string to remove row, or trigger refresh
        # We can return nothing and let HTMX remove the row if target is the row
    else:
        trigger_toast(response, "Failed to remove schedule", "error")
        
    return response

@router.put("/schedule/{job_id}")
async def update_schedule(job_id: str, request: Request, cron: str = Form(...)):
    success = update_job(job_id, cron)
    
    if not success:
        response = Response(status_code=200) # HTMX
        # We assume failure here is validation or job not found.
        # Ideally update_job returns specific error or we validate first.
        # For now, let's validate here if we want specific message, or rely on update_job returning False for bad cron.
        # But update_job in tasks calls .reschedule matching trigger options.
        trigger_toast(response, "Failed: Invalid Cron or Job missing", "error")
        return response
    
    # Return the updated row (Read Mode)
    job = get_job_info(job_id)
    response = templates.TemplateResponse("partials/queue_row.html", {"request": request, "job": job})
    trigger_toast(response, "Schedule updated", "success")
    return response

@router.get("/partials/queue/row/{job_id}")
async def get_job_row(job_id: str, request: Request):
    """
    Returns the Read Mode row.
    """
    job = get_job_info(job_id)
    if not job:
         return Response("") # Job gone?
    return templates.TemplateResponse("partials/queue_row.html", {"request": request, "job": job})

@router.get("/partials/queue/row/{job_id}/edit")
async def get_job_row_edit(job_id: str, request: Request):
    """
    Returns the Edit Mode row.
    """
    job = get_job_info(job_id)
    if not job:
         return Response("")
    return templates.TemplateResponse("partials/queue_row_edit.html", {"request": request, "job": job})

@router.get("/history")
async def get_global_history(request: Request):
    """
    Returns global history for all playbooks.
    """
    with Session(engine) as session:
        statement = select(JobRun).order_by(desc(JobRun.start_time)).limit(50)
        runs = session.exec(statement).all()
        
    return templates.TemplateResponse("history.html", {
        "request": request, 
        "runs": runs
    })

@router.delete("/history/run/{run_id}")
async def delete_run(run_id: int):
    with Session(engine) as session:
        run = session.get(JobRun, run_id)
        if run:
            session.delete(run)
            session.commit()
            return Response(status_code=200)
        return Response(status_code=404)

@router.get("/history/{playbook_name}")
async def get_history(playbook_name: str, request: Request):
    with Session(engine) as session:
        statement = select(JobRun).where(JobRun.playbook == playbook_name).order_by(desc(JobRun.start_time)).limit(10)
        runs = session.exec(statement).all()
        
    return templates.TemplateResponse("partials/history_list_modal.html", {
        "request": request, 
        "manual_runs": runs, 
        "playbook_name": playbook_name
    })

@router.get("/history/run/{run_id}")
async def get_run_details(run_id: int, request: Request):
    with Session(engine) as session:
        run = session.get(JobRun, run_id)
        
    if not run:
        return Response("Run not found", status_code=404)

    return templates.TemplateResponse("partials/log_viewer_modal.html", {
        "request": request,
        "run": run
    })

@router.get("/settings/retention")
async def get_retention_settings(request: Request):
    playbooks_data = PlaybookService.list_playbooks()
    
    with Session(engine) as session:
        # Get Global
        g_conf = session.get(GlobalConfig, "global_retention_days")
        global_retention = int(g_conf.value) if g_conf else 30
        
        g_runs_conf = session.get(GlobalConfig, "global_max_runs")
        global_max_runs = int(g_runs_conf.value) if g_runs_conf else 50
        
        # Get Overrides
        playbooks = []
        for pb in playbooks_data:
            name = pb['name']
            p_conf = session.get(PlaybookConfig, name)
            retention = p_conf.retention_days if p_conf else ""
            max_runs = p_conf.max_runs if p_conf and p_conf.max_runs is not None else ""
            playbooks.append({"name": name, "retention": retention, "max_runs": max_runs})
            
    return templates.TemplateResponse("partials/retention_modal.html", {
        "request": request,
        "global_retention": global_retention,
        "global_max_runs": global_max_runs,
        "playbooks": playbooks
    })

@router.post("/settings/retention")
async def save_retention_settings(request: Request):
    form = await request.form()
    global_max_runs = form.get("global_max_runs")
    
    with Session(engine) as session:
        # Save Global Retention
        if global_retention:
            g_conf = session.get(GlobalConfig, "global_retention_days")
            if not g_conf:
                g_conf = GlobalConfig(key="global_retention_days", value=str(global_retention))
            else:
                g_conf.value = str(global_retention)
            session.add(g_conf)
            
        # Save Global Max Runs
        if global_max_runs:
            g_runs_conf = session.get(GlobalConfig, "global_max_runs")
            if not g_runs_conf:
                g_runs_conf = GlobalConfig(key="global_max_runs", value=str(global_max_runs))
            else:
                g_runs_conf.value = str(global_max_runs)
            session.add(g_runs_conf)
            
        # Group Override Data
        # form fields: retention_{name}, max_runs_{name}
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
                
        # Save Overrides
        for pb_name, values in overrides.items():
            retention_val = values.get('retention')
            max_runs_val = values.get('max_runs')
            
            p_conf = session.get(PlaybookConfig, pb_name)
            
            if (retention_val and retention_val.strip()) or (max_runs_val and max_runs_val.strip()):
                if not p_conf:
                    p_conf = PlaybookConfig(playbook_name=pb_name)
                
                if retention_val and retention_val.strip():
                    p_conf.retention_days = int(retention_val)
                    
                if max_runs_val and max_runs_val.strip():
                    p_conf.max_runs = int(max_runs_val)
                else:
                    p_conf.max_runs = None # Reset if empty? Or keep? Let's assume empty means remove override. 
                    # Actually if partial usage, field needs default.
                    # Current logic: if empty, we might want to unset it.
                    
                session.add(p_conf)
            else:
                # If both empty, delete config?
                # Only if p_conf exists and we are updating
                 if p_conf and not (retention_val and retention_val.strip()) and not (max_runs_val and max_runs_val.strip()):
                     session.delete(p_conf)

        session.commit()
        
    response = Response(status_code=200)
    trigger_toast(response, "Retention settings saved", "success")
    return response

@router.post("/lint")
async def lint_playbook(request: Request):
    """
    Accepts content and returns Ace Editor annotations.
    """
    form = await request.form()
    content = form.get("content")
    
    if not content:
        return []
        
    annotations = await LinterService.lint_playbook_content(content)
    return annotations
