from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services import RunnerService
import logging
from datetime import datetime, timezone, timedelta
import math
from app.database import engine
from sqlmodel import Session, select, desc
from app.models import JobRun, PlaybookConfig, GlobalConfig

logger = logging.getLogger(__name__)

# Job Store Configuration
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

async def execute_playbook_job(playbook_name: str, **kwargs):
    """
    The function triggering the actual playbook execution.
    """
    logger.info(f"Scheduler: Starting job for {playbook_name}")
    result = await RunnerService.run_playbook_headless(playbook_name)
    
    status = "SUCCESS" if result['success'] else "FAILED"
    logger.info(f"Scheduler: Job {playbook_name} finished with status {status}. RC: {result['rc']}")
    # Phase 5: Here we would save to history DB

def setup_scheduler():
    """
    Starts the scheduler.
    """
    if not scheduler.running:
        scheduler.start()
        
        # Add cleanup job (runs daily)
        if not scheduler.get_job("cleanup_logs"):
            scheduler.add_job(
                cleanup_logs,
                IntervalTrigger(days=1),
                id="cleanup_logs",
                name="Cleanup Old Logs",
                replace_existing=True
            )
            
        logger.info("Scheduler started.")

def cleanup_logs():
    """
    Deletes logs older than retention policy.
    """
    logger.info("Starting log cleanup...")
    with Session(engine) as session:
        # Get Global Retention
        global_conf = session.get(GlobalConfig, "global_retention_days")
        global_days = int(global_conf.value) if global_conf else 30
        
        # Get Global Max Runs
        global_runs_conf = session.get(GlobalConfig, "global_max_runs")
        global_max_runs = int(global_runs_conf.value) if global_runs_conf else 50
        
        # Get all playbooks executed
        statement = select(JobRun.playbook).distinct()
        playbooks = session.exec(statement).all()
        
        deleted_count = 0
        
        for playbook in playbooks:
            # Check for override
            pb_conf = session.get(PlaybookConfig, playbook)
            days = pb_conf.retention_days if pb_conf else global_days
            max_runs = pb_conf.max_runs if pb_conf and pb_conf.max_runs is not None else global_max_runs
            
            # 1. Delete by Time
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            delete_stmt = select(JobRun).where(JobRun.playbook == playbook).where(JobRun.start_time < cutoff_date)
            runs_to_delete = session.exec(delete_stmt).all()
            
            for run in runs_to_delete:
                session.delete(run)
                deleted_count += 1
            
            # 2. Delete by Count (Keep latest N)
            # Fetch IDs of the latest N runs
            keep_stmt = select(JobRun.id).where(JobRun.playbook == playbook).order_by(desc(JobRun.start_time)).limit(max_runs)
            keep_ids = session.exec(keep_stmt).all()
            
            if keep_ids:
                # Delete anything NOT in keep_ids for this playbook
                delete_count_stmt = select(JobRun).where(JobRun.playbook == playbook).where(JobRun.id.not_in(keep_ids))
                runs_overflow = session.exec(delete_count_stmt).all()
                
                for run in runs_overflow:
                    session.delete(run)
                    deleted_count += 1
                
        session.commit()
    logger.info(f"Cleanup finished. Deleted {deleted_count} logs.")

def add_playbook_job(playbook_name: str, cron_expression: str):
    """
    Adds a cron job for a playbook.
    Example cron: "0 3 * * *"
    """
    try:
        # We use the playbook_name as job_id to enforce 1 schedule per playbook (optional, but cleaner for now)
        # Or allow multiple? User might want morning and evening.
        # Let's generate a unique ID based on playbook + minimal hash, or just let APScheduler handle ID?
        # User requirement: "Create a modal to accept Cron".
        # Let's assume we want to support multiple schedules.
        
        job = scheduler.add_job(
            execute_playbook_job,
            CronTrigger.from_crontab(cron_expression),
            args=[playbook_name],
            kwargs={"cron_expr": cron_expression},
            name=f"Run {playbook_name}",
            replace_existing=False
        )
        return job.id
    except Exception as e:
        logger.error(f"Failed to add job: {e}")
        return None

def format_timedelta(dt: datetime) -> str:
    if not dt:
        return "Not Scheduled"
    
    # Ensure timezone awareness for comparison
    now = datetime.now(dt.tzinfo)
    diff = dt - now
    
    seconds = diff.total_seconds()
    if seconds < 0:
         return "Overdue"
    
    if seconds < 60:
        return "In < 1 minute"
    
    minutes = math.ceil(seconds / 60)
    if minutes < 60:
        return f"In {minutes} mins"
    
    hours = math.ceil(minutes / 60)
    if hours < 24:
        return f"In {hours} hours"
        
    days = math.ceil(hours / 24)
    return f"In {days} days"

def list_jobs():
    """
    Returns list of active jobs.
    """
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "next_run_human": format_timedelta(job.next_run_time),
            "args": job.args
        })
    return jobs

def remove_job(job_id: str):
    """
    Removes a job.
    """
    try:
        scheduler.remove_job(job_id)
        return True
    except Exception:
        return False

def update_job(job_id: str, cron_expression: str):
    """
    Updates the cron trigger for an existing job.
    """
    try:
        scheduler.reschedule_job(
            job_id,
            trigger=CronTrigger.from_crontab(cron_expression)
        )
        scheduler.modify_job(job_id, kwargs={"cron_expr": cron_expression})
        return True
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")
        return False

def get_job_info(job_id: str):
    """
    Returns info for a single job.
    """
    job = scheduler.get_job(job_id)
    if not job:
        return None
    return {
        "id": job.id,
        "name": job.name,
        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        "next_run_human": format_timedelta(job.next_run_time),
        "args": job.args,
        "cron": job.kwargs.get("cron_expr", "* * * * *")
    }
