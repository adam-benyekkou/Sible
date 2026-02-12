from sqlmodel import Session
from app.core.database import engine
from typing import Generator
from fastapi import Depends
from app.services import PlaybookService, RunnerService, HistoryService, SettingsService, NotificationService

def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

def get_playbook_service(db: Session = Depends(get_db)) -> PlaybookService:
    return PlaybookService(db)

def get_runner_service(db: Session = Depends(get_db)) -> RunnerService:
    return RunnerService(db)

def get_history_service(db: Session = Depends(get_db)) -> HistoryService:
    return HistoryService(db)

def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    return SettingsService(db)

def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


from app.core.security import get_current_user, RoleChecker

def requires_role(role: str | list[str]):
    roles = role if isinstance(role, list) else [role]
    return RoleChecker(roles)
