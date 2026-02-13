from fastapi import APIRouter, Request, Response, Form, Depends
from fastapi.responses import HTMLResponse
from typing import Any, Optional, List
from app.templates import templates
from app.core.config import get_settings
from app.services import SchedulerService
from app.dependencies import get_db, requires_role, check_default_password
from app.models import User
from sqlmodel import Session, select
from app.utils.htmx import trigger_toast

settings = get_settings()
router = APIRouter()

@router.get("/schedules", response_class=HTMLResponse)
async def get_queue_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(requires_role(["admin", "operator"])),
    show_default_password_warning: bool = Depends(check_default_password)
) -> Response:
    """Renders the main scheduled jobs (queue) management page.

    Args:
        request: FastAPI request.
        db: Database session.
        current_user: Authenticated operator+.
        show_default_password_warning: Whether to show the default password warning.

    Returns:
        TemplateResponse for the schedules page.
    """
    from app.models import Host
    jobs = SchedulerService.list_jobs()
    
    # Get groups for icon logic
    groups = db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()

    return templates.TemplateResponse("schedules.html", {
        "request": request, 
        "jobs": jobs, 
        "active_tab": "queue",
        "groups": groups,
        "show_default_password_warning": show_default_password_warning
    })

@router.post("/schedule")
async def create_schedule(
    playbook: str = Form(...), 
    cron: str = Form(...),
    target: Optional[str] = Form(default=None),
    extra_vars: Optional[str] = Form(default=None),
    current_user: Any = Depends(requires_role(["admin"]))
) -> Response:
    """Creates a new scheduled job for a playbook.

    Why: Validates the cron expression via APScheduler to ensure the job
    can be properly persisted and triggered. Returns a toast on error.

    Args:
        playbook: Path to the target playbook.
        cron: Standard cron expression.
        target: Optional host/group limit.
        extra_vars: Optional JSON string of variables.
        current_user: Admin access required.

    Returns:
        Response with success/failure toast and modal close trigger.
    """
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
    current_user: Any = Depends(requires_role(["admin"]))
) -> Response:
    """Permanently removes a scheduled job from the queue.

    Args:
        job_id: Unique identifier for the APScheduler job.
        current_user: Admin access required.

    Returns:
        Response with status toast.
    """
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
    cron: Optional[str] = Form(default=None),
    target: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: Any = Depends(requires_role(["admin"]))
) -> Response:
    """Updates the recurrence or target of an existing scheduled job.

    Args:
        job_id: Target job ID.
        request: Request object.
        cron: New cron expression.
        target: New host/group limit.
        db: Database session.
        current_user: Admin access required.

    Returns:
        TemplateResponse for the updated row with OOB triggers.
    """
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
        groups = db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()
             
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
    current_user: Any = Depends(requires_role(["admin"]))
) -> Response:
    """Temporarily halts the execution of a scheduled job.

    Args:
        job_id: Target job ID.
        request: Request object.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Updated row fragment showing the 'Paused' status.
    """
    success = SchedulerService.pause_job(job_id)
    if not success:
        return Response(status_code=400)
    
    # Return updated row
    job = SchedulerService.get_job_info(job_id)
    
    from app.models import Host
    groups = db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()

    return templates.TemplateResponse("partials/schedules_row.html", {"request": request, "job": job, "groups": groups})

@router.post("/schedule/{job_id}/resume")
async def resume_schedule(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Any = Depends(requires_role(["admin"]))
) -> Response:
    """Resumes a previously paused scheduled job.

    Args:
        job_id: Target job ID.
        request: Request object.
        db: Database session.
        current_user: Admin access required.

    Returns:
        Updated row fragment showing the active status.
    """
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
) -> Response:
    """Returns the HTML fragment for a single job row.

    Args:
        job_id: Target job ID.
        request: Request object.
        db: Database session.
        current_user: Authenticated operator+.

    Returns:
        Row template response.
    """
    job = SchedulerService.get_job_info(job_id)
    if not job: return Response("")
    
    # Get groups for icon logic
    from app.models import Host
    groups = db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all()
    
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
) -> Response:
    """Renders the inline edit form or modal for a scheduled job.

    Args:
        job_id: Target job ID.
        request: Request object.
        db: Database session.
        current_user: Admin access required.

    Returns:
        TemplateResponse for the edit modal content.
    """
    from app.models import Host
    job = SchedulerService.get_job_info(job_id)
    if not job: return Response(status_code=404)
    
    groups = sorted(db.exec(select(Host.group_name).where(Host.group_name.is_not(None)).distinct()).all())
    servers = sorted(db.exec(select(Host.alias)).all())
    
    return templates.TemplateResponse("partials/schedules_modal.html", {
        "request": request, 
        "job": job,
        "groups": groups,
        "servers": servers
    })
