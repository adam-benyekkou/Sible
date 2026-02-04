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

class PlaybookConfig(SQLModel, table=True):
    playbook_name: str = Field(primary_key=True)
    retention_days: int = Field(default=30)
    max_runs: Optional[int] = Field(default=50)

class GlobalConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str

class AppSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    app_name: str = Field(default="Sible")
    global_retention_days: int = Field(default=30)
    global_max_runs: int = Field(default=50)
    apprise_url: Optional[str] = Field(default=None)
    notify_on_success: bool = Field(default=False)
    notify_on_failure: bool = Field(default=True)
    logo_path: Optional[str] = Field(default=None)
    favicon_path: Optional[str] = Field(default=None)
    
    # Authentication
    auth_enabled: bool = Field(default=False)
    auth_username: str = Field(default="admin")
    auth_password: str = Field(default="admin")
