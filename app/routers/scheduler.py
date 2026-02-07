from fastapi import APIRouter, Request, Response, Form, Depends
from app.templates import templates
from app.core.config import get_settings
from app.services import SchedulerService
from app.dependencies import get_db, requires_role
from app.models import User
from app.utils.htmx import trigger_toast

settings = get_settings()
router = APIRouter()

@router.get("/queue")
async def get_queue_view(
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    jobs = SchedulerService.list_jobs()
    return templates.TemplateResponse("queue.html", {"request": request, "jobs": jobs, "active_tab": "queue"})

@router.post("/schedule")
async def create_schedule(
    playbook: str = Form(...), 
    cron: str = Form(...),
    current_user: object = Depends(requires_role(["admin"]))
):
    job_id = SchedulerService.add_playbook_job(playbook, cron)
    response = Response(status_code=200)
    if job_id:
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
    current_user: object = Depends(requires_role(["admin"]))
):
    import logging
    logger = logging.getLogger("uvicorn.error")
    logger.info(f"Update schedule request for {job_id}. Cron: '{cron}'")

    if cron is None:
        logger.error(f"Cron is None for job {job_id}")
        response = Response(status_code=204)
        trigger_toast(response, "Failed: Missing form data", "error")
        return response

    try:
        success = SchedulerService.update_job(job_id, cron)
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
             
        response = templates.TemplateResponse("partials/queue_row.html", {"request": request, "job": job})
        trigger_toast(response, "Schedule updated", "success")
        return response
    except Exception as e:
        logger.error(f"Exception updating job {job_id}: {e}")
        response = Response(status_code=204)
        trigger_toast(response, f"Error: {str(e)}", "error")
        return response

@router.get("/partials/queue/row/{job_id}")
async def get_job_row(
    job_id: str, 
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator"]))
):
    job = SchedulerService.get_job_info(job_id)
    if not job: return Response("")
    return templates.TemplateResponse("partials/queue_row.html", {"request": request, "job": job})

@router.get("/partials/queue/row/{job_id}/edit")
async def get_job_row_edit(
    job_id: str, 
    request: Request,
    current_user: User = Depends(requires_role(["admin"]))
):
    job = SchedulerService.get_job_info(job_id)
    if not job: return Response(status_code=404)
    return templates.TemplateResponse("partials/queue_row_edit.html", {"request": request, "job": job})
