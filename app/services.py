from pathlib import Path
from typing import List, Optional
import os
import re

PLAYBOOKS_DIR = Path("playbooks")

class PlaybookService:
    @staticmethod
    def _validate_path(name: str) -> Optional[Path]:
        """
        Validates the filename to prevent path traversal and ensures it's a YAML file.
        Returns the resolved Path if valid, None otherwise.
        """
        # 1. Allow alphanumeric, dashes, underscores, dots
        # This prevents ".." or weird characters.
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
            return None
            
        # 2. Check extension
        if not name.endswith((".yaml", ".yml")):
            return None
        
        # 3. Resolve path and ensure it's inside PLAYBOOKS_DIR
        try:
            target_path = (PLAYBOOKS_DIR / name).resolve()
            # Ensure the resolved path starts with the resolved PLAYBOOKS_DIR
            if not str(target_path).startswith(str(PLAYBOOKS_DIR.resolve())):
                return None
            return target_path
        except Exception:
            return None

    @staticmethod
    def list_playbooks() -> List[str]:
        """
        Scans the playbooks directory and returns a list of .yaml/.yml files.
        """
        if not PLAYBOOKS_DIR.exists():
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            return []
            
        extensions = {".yaml", ".yml"}
        playbooks = [
            f.name for f in PLAYBOOKS_DIR.iterdir() 
            if f.is_file() and f.suffix.lower() in extensions
        ]
        return sorted(playbooks)

    @staticmethod
    def get_playbook_content(name: str) -> Optional[str]:
        """
        Reads the content of a playbook.
        """
        file_path = PlaybookService._validate_path(name)
        if not file_path or not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    @staticmethod
    def save_playbook_content(name: str, content: str) -> bool:
        """
        Saves content to a playbook file.
        """
        file_path = PlaybookService._validate_path(name)
        if not file_path:
            return False
            
        try:
            # Ensure directory exists (helper for first save)
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            
            file_path.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    @staticmethod
    def create_playbook(name: str) -> bool:
        """
        Creates a new empty playbook if it doesn't exist.
        """
        if not name.endswith((".yaml", ".yml")):
            name += ".yaml"
            
        file_path = PlaybookService._validate_path(name)
        if not file_path:
            return False
            
        if file_path.exists():
            return False # Already exists
            
        try:
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            file_path.write_text("---\n- name: New Playbook\n  hosts: localhost\n  tasks:\n    - debug:\n        msg: 'Hello World'\n", encoding="utf-8")
            return True
        except OSError:
            return False

    @staticmethod
    def delete_playbook(name: str) -> bool:
        """
        Deletes a playbook file.
        """
        file_path = PlaybookService._validate_path(name)
        if not file_path or not file_path.exists():
            return False
            
        try:
            file_path.unlink()
            return True
        except OSError:
            return False
