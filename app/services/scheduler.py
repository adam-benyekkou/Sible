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

async def execute_playbook_job(playbook_name: str, **kwargs):
    """
    The function triggering the actual playbook execution.
    """
    logger.info(f"Scheduler: Starting job for {playbook_name}")
    with Session(engine) as session:
        runner_service = RunnerService(session)
        result = await runner_service.run_playbook_headless(playbook_name)
    
    status = "SUCCESS" if result['success'] else "FAILED"
    logger.info(f"Scheduler: Job {playbook_name} finished with status {status}. RC: {result['rc']}")

class SchedulerService:
    @staticmethod
    def start():
        if not scheduler.running:
            scheduler.start()
            # Cleanup legacy jobs if they exist
            try:
                for job_id in ["cleanup_logs", "refresh_inventory_status"]:
                    if scheduler.get_job(job_id):
                        scheduler.remove_job(job_id)
                        logger.info(f"Scheduler: Removed legacy job {job_id}")
            except Exception as e:
                logger.warning(f"Scheduler: Failed to cleanup legacy jobs: {e}")
                
            logger.info("Scheduler started.")

    @staticmethod
    def shutdown():
        scheduler.shutdown()

    @staticmethod
    def add_playbook_job(playbook_name: str, cron_expression: str):
        try:
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

    @staticmethod
    def list_jobs():
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "next_run_human": SchedulerService.format_timedelta(job.next_run_time),
                "args": job.args
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
    def update_job(job_id: str, cron_expression: str):
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

    @staticmethod
    def get_job_info(job_id: str):
        job = scheduler.get_job(job_id)
        if not job:
            return None
        return {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "next_run_human": SchedulerService.format_timedelta(job.next_run_time),
            "args": job.args,
            "cron": job.kwargs.get("cron_expr", "* * * * *")
        }

    @staticmethod
    def format_timedelta(dt: datetime) -> str:
        if not dt: return "Not Scheduled"
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
