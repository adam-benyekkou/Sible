from typing import Any, Optional
from sqlmodel import Session
from typing import Any, Optional
from app.core.config import get_settings
from app.models import AppSettings
from pathlib import Path
import shutil
import sys
import os
import asyncio

settings_conf = get_settings()

class SettingsService:
    """Manages application-wide settings and environment variables.

    This service handles the retrieval and update of global configuration,
    as well as the management of custom environment variables (including secrets)
    that are passed to Ansible executions.
    """
    def __init__(self, db: Session):
        """Initializes the service.

        Args:
            db: Database session for settings persistence.
        """
        self.db = db

    def get_settings(self) -> AppSettings:
        """Retrieves global application settings, creating a default record if missing.

        Why: Ensures that the application always has a valid configuration
        state without requiring manual database initialization.

        Returns:
            The unique AppSettings record (ID=1).
        """
        settings = self.db.get(AppSettings, 1)
        if not settings:
            settings = AppSettings(id=1)
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        return settings

    def update_settings(self, data: dict[str, Any]) -> AppSettings:
        """Updates the global application settings.

        Args:
            data: A dictionary of setting names and their new values.

        Returns:
            The updated AppSettings record.
        """
        settings = self.get_settings()
        for k, v in data.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_env_vars(self) -> list[Any]:
        """Retrieves all custom environment variables.

        Returns:
            A list of EnvVar records.
        """
        from app.models import EnvVar
        from sqlmodel import select
        return self.db.exec(select(EnvVar)).all()

    def create_env_var(self, key: str, value: str, is_secret: bool) -> Any:
        """Creates a new environment variable, encrypting it if it's a secret.

        Args:
            key: The variable name (e.g., 'ANSIBLE_HOST_KEY_CHECKING').
            value: The variable value.
            is_secret: If True, the value will be encrypted at rest.

        Returns:
            The newly created EnvVar record.
        """
        from app.models import EnvVar
        from app.core.security import encrypt_secret
        
        stored_value = encrypt_secret(value) if is_secret else value
        env_var = EnvVar(key=key, value=stored_value, is_secret=is_secret)
        self.db.add(env_var)
        self.db.commit()
        return env_var

    def delete_env_var(self, env_id: int) -> Optional[str]:
        """Deletes an environment variable by ID.

        Args:
            env_id: The ID of the variable to delete.

        Returns:
            The key of the deleted variable, or None if not found.
        """
        from app.models import EnvVar
        env_var = self.db.get(EnvVar, env_id)
        if env_var:
            key = env_var.key
            self.db.delete(env_var)
            self.db.commit()
            return key
        return None

    def update_env_var(
        self, 
        env_id: int, 
        key: str, 
        value: str, 
        is_secret: bool
    ) -> Optional[Any]:
        """Updates an existing environment variable, handling encryption for secrets.

        Why: Allows users to rotate secrets or update configuration without
        deleting and recreating records.

        Args:
            env_id: The ID of the variable to update.
            key: New key name.
            value: New value (if empty for a secret, the old value is kept).
            is_secret: New secret status.

        Returns:
            The updated EnvVar record, or None if not found.
        """
        from app.models import EnvVar
        from app.core.security import encrypt_secret
        env_var = self.db.get(EnvVar, env_id)
        if env_var:
            env_var.key = key
            if is_secret:
                env_var.is_secret = True
                if value.strip():
                    env_var.value = encrypt_secret(value)
            else:
                env_var.is_secret = False
                env_var.value = value
                
            self.db.add(env_var)
            self.db.commit()
            self.db.refresh(env_var)
            return env_var
        return None

