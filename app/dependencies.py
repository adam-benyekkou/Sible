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


from app.core.security import get_current_user, RoleChecker, is_using_default_password
from app.models import User

def requires_role(role: str | list[str]):
    roles = role if isinstance(role, list) else [role]
    return RoleChecker(roles)

def check_default_password(current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))) -> bool:
    """Dependency that checks if the current user is using a default password.
    
    Returns:
        True if the user is using a default password (username == password), False otherwise.
    """
    return is_using_default_password(current_user)
