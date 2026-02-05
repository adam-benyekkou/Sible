from sqlmodel import Session, select, desc, delete
from app.models import JobRun
from typing import List, Optional

class HistoryService:
    def __init__(self, db: Session):
        self.db = db

    def get_recent_runs(self, limit: int = 50) -> List[JobRun]:
        return self.db.exec(select(JobRun).order_by(desc(JobRun.start_time)).limit(limit)).all()

    def get_run(self, run_id: int) -> Optional[JobRun]:
        return self.db.get(JobRun, run_id)

    def delete_run(self, run_id: int) -> bool:
        run = self.get_run(run_id)
        if run:
            self.db.delete(run)
            self.db.commit()
            return True
        return False

    def delete_all_runs(self):
        self.db.exec(delete(JobRun))
        self.db.commit()

    def get_playbook_runs(self, playbook_name: str, limit: int = 50) -> List[JobRun]:
        statement = select(JobRun).where(JobRun.playbook == playbook_name).order_by(desc(JobRun.start_time)).limit(limit)
        return self.db.exec(statement).all()

    def delete_playbook_runs(self, playbook_name: str):
        statement = delete(JobRun).where(JobRun.playbook == playbook_name)
        self.db.exec(statement)
        self.db.commit()
