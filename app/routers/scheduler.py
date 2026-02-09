from fastapi import APIRouter, Request, Response, Form, Depends
from app.templates import templates
from app.core.config import get_settings
from app.services import SchedulerService
from app.dependencies import get_db, requires_role
from app.models import User
from sqlmodel import Session, select
from app.utils.htmx import trigger_toast

settings = get_settings()
router = APIRouter()

@router.get("/schedules")
async def get_queue_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    from app.models import Host
    jobs = SchedulerService.list_jobs()
    
    # Get groups for icon logic
    hosts = db.exec(select(Host)).all()
    groups = list(set(h.group_name for h in hosts if h.group_name))

    return templates.TemplateResponse("schedules.html", {
        "request": request, 
        "jobs": jobs, 
        "active_tab": "queue",
        "groups": groups
    })

@router.post("/schedule")
async def create_schedule(
    playbook: str = Form(...), 
    cron: str = Form(...),
    target: str = Form(default=None),
    extra_vars: str = Form(default=None),
    current_user: object = Depends(requires_role(["admin"]))
):
    job_id = SchedulerService.add_playbook_job(playbook, cron, target=target, extra_vars=extra_vars)
    response = Response(status_code=200)
    if job_id:
        import json
        response.headers["HX-Trigger"] = json.dumps({"close-modal": True})
        trigger_toast(response, f"Scheduled {playbook}", "success")
    else:
        trigger_toast(response, "Invalid Cron Expression", "error")
    return response

@router.delete("/schedule/{job_id}")
async def delete_schedule(
    job_id: str,
    current_user: object = Depends(requires_role(["admin"]))
):
    success = SchedulerService.remove_job(job_id)
    response = Response(status_code=200)
    if success:
        trigger_toast(response, "Schedule removed", "success")
    else:
        trigger_toast(response, "Failed to remove", "error")
    return response

@router.put("/schedule/{job_id}")
async def update_schedule(
    job_id: str, 
    request: Request, 
    cron: str = Form(default=None),
    target: str = Form(default=None),
    db: Session = Depends(get_db),
    current_user: object = Depends(requires_role(["admin"]))
):
    import logging
    logger = logging.getLogger("uvicorn.error")
    logger.info(f"Update schedule request for {job_id}. Cron: '{cron}'")

    if cron is None and target is None:
        logger.error(f"Cron and target are None for job {job_id}")
        response = Response(status_code=204)
        trigger_toast(response, "Failed: Missing form data", "error")
        return response

    try:
        success = SchedulerService.update_job(job_id, cron, target=target)
        logger.info(f"Update job result for {job_id}: {success}")
        
        if not success:
            response = Response(status_code=204)
            trigger_toast(response, "Failed: Invalid Cron", "error")
            return response
            
        job = SchedulerService.get_job_info(job_id)
        if not job:
             logger.error(f"Job {job_id} not found after update")
             response = Response(status_code=204)
             trigger_toast(response, "Job not found after update", "error")
             return response
        
        from app.models import Host
        hosts = db.exec(select(Host)).all()
        groups = list(set(h.group_name for h in hosts if h.group_name))
             
        response = templates.TemplateResponse("partials/schedules_row.html", {"request": request, "job": job, "groups": groups})
        
        # Trigger modal close and toast
        import json
        response.headers["HX-Trigger"] = json.dumps({"close-modal": True})
        trigger_toast(response, "Schedule updated", "success")
        
        return response
    except Exception as e:
        logger.error(f"Exception updating job {job_id}: {e}")
        response = Response(status_code=204)
        trigger_toast(response, f"Error: {str(e)}", "error")
        return response

@router.post("/schedule/{job_id}/pause")
async def pause_schedule(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: object = Depends(requires_role(["admin"]))
):
    success = SchedulerService.pause_job(job_id)
    if not success:
        return Response(status_code=400)
    
    # Return updated row
    job = SchedulerService.get_job_info(job_id)
    
    from app.models import Host
    hosts = db.exec(select(Host)).all()
    groups = list(set(h.group_name for h in hosts if h.group_name))

    return templates.TemplateResponse("partials/schedules_row.html", {"request": request, "job": job, "groups": groups})

@router.post("/schedule/{job_id}/resume")
async def resume_schedule(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: object = Depends(requires_role(["admin"]))
):
    success = SchedulerService.resume_job(job_id)
    if not success:
        return Response(status_code=400)
    
    # Return updated row
    job = SchedulerService.get_job_info(job_id)

    from app.models import Host
    hosts = db.exec(select(Host)).all()
    groups = list(set(h.group_name for h in hosts if h.group_name))

    return templates.TemplateResponse("partials/schedules_row.html", {"request": request, "job": job, "groups": groups})

@router.get("/partials/schedules/row/{job_id}")
async def get_job_row(
    job_id: str, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    from app.services.inventory import InventoryService
    job = SchedulerService.get_job_info(job_id)
    if not job: return Response("")
    
    # Get groups for icon logic
    content = InventoryService.get_inventory_content()
    # A simple way to get groups without parsing content again if we have a DB helper,
    # but let's use the DB since we have the session
    from app.models import Host
    hosts = db.exec(select(Host)).all()
    groups = list(set(h.group_name for h in hosts if h.group_name))
    
    return templates.TemplateResponse("partials/schedules_row.html", {
        "request": request, 
        "job": job,
        "groups": groups
    })

@router.get("/partials/schedules/row/{job_id}/edit")
async def get_job_row_edit(
    job_id: str, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin"]))
):
    from app.models import Host
    job = SchedulerService.get_job_info(job_id)
    if not job: return Response(status_code=404)
    
    hosts = db.exec(select(Host)).all()
    groups = sorted(list(set(h.group_name for h in hosts if h.group_name)))
    servers = sorted([h.alias for h in hosts])
    
    return templates.TemplateResponse("partials/schedules_modal.html", {
        "request": request, 
        "job": job,
        "groups": groups,
        "servers": servers
    })
