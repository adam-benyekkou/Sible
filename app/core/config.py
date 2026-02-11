from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pathlib import Path

class Settings(BaseSettings):
    APP_NAME: str = "Sible"
    VERSION: str = "1.0.0"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    PLAYBOOKS_DIR: Path = BASE_DIR / "playbooks"
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    DATABASE_URL: str = "sqlite:///sible.db"
    SECRET_KEY: str = "sible-secret-key-change-me"
    
    # Docker Settings
    USE_DOCKER: bool = True
    DOCKER_IMAGE: str = "quay.io/ansible/ansible-runner:latest"
    DOCKER_WORKSPACE_PATH: str = "/ansible"
    HOST_WORKSPACE_PATH: Optional[str] = None
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
