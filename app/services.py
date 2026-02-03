from pathlib import Path
from typing import List, Optional
import os

PLAYBOOKS_DIR = Path("playbooks")

class PlaybookService:
    @staticmethod
    def list_playbooks() -> List[str]:
        """
        Scans the playbooks directory and returns a list of .yaml/.yml files.
        """
        if not PLAYBOOKS_DIR.exists():
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
        file_path = PLAYBOOKS_DIR / name
        if not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    @staticmethod
    def save_playbook_content(name: str, content: str) -> bool:
        """
        Saves content to a playbook file.
        """
        if not name.endswith((".yaml", ".yml")):
            return False
            
        try:
            # Ensure directory exists
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            
            file_path = PLAYBOOKS_DIR / name
            file_path.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False
