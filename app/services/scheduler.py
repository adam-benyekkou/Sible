from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Any, Optional
from sqlmodel import Session, select
import logging
from datetime import datetime
import math
from app.core.config import get_settings
from app.core.database import engine
from app.services.runner import RunnerService

settings = get_settings()
logger = logging.getLogger(__name__)

# Job Store Configuration
# Use the same database URL as the rest of the app for consistency
jobstores = {
    'default': SQLAlchemyJobStore(url=settings.DATABASE_URL)
}

scheduler = AsyncIOScheduler(jobstores=jobstores)

async def periodic_status_refresh() -> None:
    """Wrapper for periodic inventory status refresh with fresh session.

    Why: Ensures that the host reachability status (ping) in the Dashboard
    stays accurate over time without requiring user-initiated pings.
    """
    from app.services.inventory import InventoryService
    from app.core.database import engine
    logger.info("Scheduler: Running periodic inventory status refresh")
    with Session(engine) as session:
        await InventoryService.refresh_all_statuses(session)


async def execute_playbook_job(playbook_name: str, **kwargs: Any) -> None:
    """The function triggering the actual playbook execution for a scheduled job.

    Why: This function bridge the APScheduler call to the Sible RunnerService,
    ensuring that jobs execute in a "headless" mode without a WebSocket
    attached, but still recording history in the database.
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
    """Manages background task scheduling using APScheduler.

    This service handles recurring jobs like health checks and scheduled
    Ansible playbook executions. It persists job state to a local SQLite
    database to ensure schedules survive application restarts.
    """
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
    def add_playbook_job(
        playbook_name: str, 
        cron_expression: str, 
        target: Optional[str] = None, 
        extra_vars: Optional[str] = None
    ) -> Optional[str]:
        """Schedules a new playbook execution using a CRON expression.

        Args:
            playbook_name: Path to the target playbook.
            cron_expression: Standard 5-field CRON string.
            target: Optional limit (host/group) for the run.
            extra_vars: JSON string of variables to pass to Ansible.

        Returns:
            The unique job ID if successfully scheduled, else None.
        """
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
    def list_jobs() -> list[dict[str, Any]]:
        """Retrieves all scheduled playbook jobs.

        Returns:
            A list of dictionary summaries for each active or paused job.
        """
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

    def update_job(
        job_id: str, 
        cron_expression: Optional[str] = None, 
        target: Optional[str] = None
    ) -> bool:
        """Updates the schedule or target for an existing job.

        Args:
            job_id: The ID of the job to modify.
            cron_expression: New CRON schedule if provided.
            target: New execution limit if provided.

        Returns:
            True if updated successfully, False on error.
        """
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
    def get_job_info(job_id: str) -> Optional[dict[str, Any]]:
        """Retrieves detailed information for a specific job.

        Args:
            job_id: The job identifier.

        Returns:
            A dictionary of job details, or None if not found.
        """
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
    def format_timedelta(dt: Optional[datetime]) -> str:
        """Converts a future datetime into a human-readable relative string.

        Args:
            dt: The future datetime to format.

        Returns:
            A string like "In 5 mins" or "In 2 days".
        """
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
