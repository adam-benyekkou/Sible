from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pathlib import Path
import os

class Settings(BaseSettings):
    APP_NAME: str = "Sible"
    VERSION: str = "1.0.0"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    PLAYBOOKS_DIR: Path = BASE_DIR / "playbooks"
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    DATABASE_URL: str = "sqlite:///sible.db"
    SECRET_KEY: str = "sible-secret-key-change-me"
    DEBUG: bool = False
    
    # Theme Settings
    THEME_LIGHT: str = "Geist Light"
    THEME_DARK: str = "Catppuccin Dark"
    
    INFRASTRUCTURE_DIR: Path = Path(os.getenv("SIBLE_INFRA_PATH", "/app/infrastructure"))
    PLAYBOOKS_DIR: Path = INFRASTRUCTURE_DIR / "playbooks"
    DATABASE_URL: str = os.getenv("SIBLE_DATABASE_URL", "sqlite:///./sible.db")
    USE_DOCKER: bool = True
    DOCKER_IMAGE: str = "quay.io/ansible/ansible-runner:latest"
    DOCKER_WORKSPACE_PATH: str = "/app/infrastructure"
    HOST_WORKSPACE_PATH: Optional[str] = os.getenv("SIBLE_HOST_INFRA_PATH")
    
    class Config:
        env_file = ".env"
        env_prefix = "SIBLE_"

@lru_cache()
def get_settings():
    return Settings()
