from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class JobRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    playbook: str
    status: str = "running"  # running, success, failed
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None
    trigger: str = "manual"  # manual, cron
    log_output: str = ""
    params: Optional[str] = Field(default=None)  # JSON string of execution parameters
