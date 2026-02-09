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
