from sqlmodel import Session, select, desc, delete
from app.models import JobRun
from typing import List, Optional

class HistoryService:
    def __init__(self, db: Session):
        self.db = db

    def get_recent_runs(self, limit: int = 50, offset: int = 0, search: str = None, status: str = None) -> tuple[List[JobRun], int]:
        query = select(JobRun).order_by(desc(JobRun.start_time))
        if search:
            query = query.where(JobRun.playbook.ilike(f"%{search}%"))
        if status and status != 'all':
            query = query.where(JobRun.status == status)
        
        # Get total count
        from sqlmodel import func
        count_query = select(func.count()).select_from(query.subquery())
        total_count = self.db.exec(count_query).one()

        from app.models import User
        users = self.db.exec(select(User)).all()

        return self.db.exec(query.offset(offset).limit(limit)).all(), total_count, users

    def get_run(self, run_id: int) -> Optional[JobRun]:
        return self.db.get(JobRun, run_id)

    def delete_run(self, run_id: int) -> bool:
        run = self.get_run(run_id)
        if run:
            self.db.delete(run)
            self.db.commit()
            return True
        return False

    def delete_all_runs(self, search: str = None, status: str = None):
        statement = delete(JobRun)
        if search:
            statement = statement.where(JobRun.playbook.ilike(f"%{search}%"))
        if status and status != 'all':
            statement = statement.where(JobRun.status == status)
        self.db.exec(statement)
        self.db.commit()

    def get_playbook_runs(self, playbook_name: str, limit: int = 50, offset: int = 0) -> tuple[List[JobRun], int]:
        statement = select(JobRun).where(JobRun.playbook == playbook_name).order_by(desc(JobRun.start_time))
        
        # Get total count
        from sqlmodel import func
        count_query = select(func.count()).select_from(statement.subquery())
        total_count = self.db.exec(count_query).one()

        from app.models import User
        users = self.db.exec(select(User)).all()

        return self.db.exec(statement.offset(offset).limit(limit)).all(), total_count, users

    def delete_playbook_runs(self, playbook_name: str):
        statement = delete(JobRun).where(JobRun.playbook == playbook_name)
        self.db.exec(statement)
        self.db.commit()

    def apply_retention_policies(self, playbook_name: Optional[str] = None):
        """
        Enforce retention policies:
        1. Remove logs older than X days.
        2. Keep at most Y most recent logs per playbook.
        """
        from app.models import AppSettings, PlaybookConfig
        from datetime import datetime, timedelta
        
        # Get global settings
        settings = self.db.exec(select(AppSettings)).first()
        if not settings:
            return
            
        global_days = settings.global_retention_days
        global_max = settings.global_max_runs
        
        # Determine which playbooks to process
        if playbook_name:
            playbooks_to_process = [playbook_name]
        else:
            # Get all unique playbook names from JobRun
            stmt = select(JobRun.playbook).distinct()
            playbooks_to_process = self.db.exec(stmt).all()
            
        for name in playbooks_to_process:
            # Get per-playbook override
            config = self.db.exec(select(PlaybookConfig).where(PlaybookConfig.playbook_name == name)).first()
            
            days_limit = config.retention_days if (config and config.retention_days is not None) else global_days
            max_limit = config.max_runs if (config and config.max_runs is not None) else global_max
            
            # 1. Prune by age
            cutoff = datetime.utcnow() - timedelta(days=days_limit)
            stmt = delete(JobRun).where(JobRun.playbook == name).where(JobRun.start_time < cutoff)
            self.db.exec(stmt)
            
            # 2. Prune by count (keep most recent)
            if max_limit > 0:
                # Find IDs of runs to keep (most recent)
                keep_stmt = select(JobRun.id).where(JobRun.playbook == name).order_by(desc(JobRun.start_time)).limit(max_limit)
                keep_ids = self.db.exec(keep_stmt).all()
                
                if keep_ids:
                    # Delete runs for this playbook that are NOT in the keep list
                    del_stmt = delete(JobRun).where(JobRun.playbook == name).where(JobRun.id.not_in(keep_ids))
                    self.db.exec(del_stmt)
                    
        self.db.commit()
