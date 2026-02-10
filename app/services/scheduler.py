from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.runner import RunnerService
import logging
from datetime import datetime
import math
from app.core.database import engine
from sqlmodel import Session
from app.services.runner import RunnerService

logger = logging.getLogger(__name__)

# Job Store Configuration
jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

async def periodic_status_refresh():
    """
    Wrapper for periodic inventory status refresh with fresh session.
    """
    from app.services.inventory import InventoryService
    from app.core.database import engine
    logger.info("Scheduler: Running periodic inventory status refresh")
    with Session(engine) as session:
        await InventoryService.refresh_all_statuses(session)


async def execute_playbook_job(playbook_name: str, **kwargs):
    """
    The function triggering the actual playbook execution.
    """
    logger.info(f"Scheduler: Starting job for {playbook_name}")
    target = kwargs.get("target")
    extra_vars = kwargs.get("extra_vars")
    
    # Parse extra_vars from JSON string if needed
    ev_dict = None
    if extra_vars:
        try:
            import json
            ev_dict = json.loads(extra_vars) if isinstance(extra_vars, str) else extra_vars
        except Exception:
            pass
    
    with Session(engine) as session:
        runner_service = RunnerService(session)
        # Pass limit if target is provided
        limit = target if target and target != 'all' else None
        result = await runner_service.run_playbook_headless(playbook_name, limit=limit, extra_vars=ev_dict, username="Scheduled")
    
    status = "SUCCESS" if result['success'] else "FAILED"
    logger.info(f"Scheduler: Job {playbook_name} finished with status {status}. RC: {result['rc']}")

class SchedulerService:
    @staticmethod
    def start():
        if not scheduler.running:
            scheduler.start()
            # Add Periodic Status Check (every 5 mins)
            scheduler.add_job(
                periodic_status_refresh,
                IntervalTrigger(minutes=5),
                id="refresh_inventory_status",
                replace_existing=True
            )
                
            logger.info("Scheduler started with periodic health checks.")

    @staticmethod
    def shutdown():
        scheduler.shutdown()

    @staticmethod
    def add_playbook_job(playbook_name: str, cron_expression: str, target: str = None, extra_vars: str = None):
        try:
            job = scheduler.add_job(
                execute_playbook_job,
                CronTrigger.from_crontab(cron_expression),
                args=[playbook_name],
                kwargs={"cron_expr": cron_expression, "target": target, "extra_vars": extra_vars},
                name=f"Run {playbook_name}",
                replace_existing=False
            )
            return job.id
        except Exception as e:
            logger.error(f"Failed to add job: {e}")
            return None

    @staticmethod
    def list_jobs():
        jobs = []
        for job in scheduler.get_jobs():
            if job.id == "refresh_inventory_status":
                continue
            
            is_paused = job.next_run_time is None
            
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "next_run_human": SchedulerService.format_timedelta(job.next_run_time) if job.next_run_time else "Paused",
                "args": job.args,
                "cron": job.kwargs.get("cron_expr", "Unknown"),
                "target": job.kwargs.get("target", "all"),
                "status": "paused" if is_paused else "running"
            })
        return jobs

    @staticmethod
    def remove_job(job_id: str):
        try:
            scheduler.remove_job(job_id)
            return True
        except Exception:
            return False

    @staticmethod
    def update_job(job_id: str, cron_expression: str = None, target: str = None):
        try:
            kwargs = {}
            if cron_expression:
                kwargs["cron_expr"] = cron_expression
                scheduler.reschedule_job(
                    job_id,
                    trigger=CronTrigger.from_crontab(cron_expression)
                )
            
            if target:
                kwargs["target"] = target
            
            if kwargs:
                scheduler.modify_job(job_id, kwargs=kwargs)
                
            return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False
            
    @staticmethod
    def pause_job(job_id: str):
        try:
            scheduler.pause_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False

    @staticmethod
    def resume_job(job_id: str):
        try:
            scheduler.resume_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False

    @staticmethod
    def get_job_info(job_id: str):
        job = scheduler.get_job(job_id)
        if not job:
            return None
            
        is_paused = job.next_run_time is None
        
        return {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time,
            "next_run_human": SchedulerService.format_timedelta(job.next_run_time) if job.next_run_time else "Paused",
            "args": job.args,
            "cron": job.kwargs.get("cron_expr", "* * * * *"),
            "target": job.kwargs.get("target", "all"),
            "status": "paused" if is_paused else "running"
        }

    @staticmethod
    def format_timedelta(dt: datetime) -> str:
        if not dt: return "Paused"
        now = datetime.now(dt.tzinfo)
        diff = dt - now
        seconds = diff.total_seconds()
        if seconds < 0: return "Overdue"
        if seconds < 60: return "In < 1 minute"
        minutes = math.ceil(seconds / 60)
        if minutes < 60: return f"In {minutes} mins"
        hours = math.ceil(minutes / 60)
        if hours < 24: return f"In {hours} hours"
        days = math.ceil(hours / 24)
        return f"In {days} days"
