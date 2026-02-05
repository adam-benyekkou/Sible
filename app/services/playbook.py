from pathlib import Path
from typing import List, Optional
from sqlmodel import Session, select, desc
import re
from app.config import get_settings
from app.models import JobRun

settings = get_settings()

class PlaybookService:
    def __init__(self, db: Session):
        self.db = db

    def _validate_path(self, name: str) -> Optional[Path]:
        if not re.match(r'^[a-zA-Z0-9_\-\.\/]+$', name):
            return None
        if not name.endswith((".yaml", ".yml")):
            return None
        try:
            target_path = (settings.PLAYBOOKS_DIR / name).resolve()
            if not str(target_path).startswith(str(settings.PLAYBOOKS_DIR.resolve())):
                return None
            return target_path
        except Exception:
            return None

    def list_playbooks(self) -> List[dict]:
        if not settings.PLAYBOOKS_DIR.exists():
            settings.PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            return []
            
        def build_tree(current_path: Path, relative_root: Path = settings.PLAYBOOKS_DIR) -> List[dict]:
            items = []
            if not current_path.exists(): return []
            entries = sorted(list(current_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            
            for entry in entries:
                rel_path = str(entry.relative_to(relative_root)).replace("\\", "/")
                if entry.is_dir():
                    children = build_tree(entry, relative_root)
                    if children:
                        items.append({
                            "type": "directory", 
                            "name": entry.name, 
                            "path": rel_path, 
                            "children": children
                        })
                elif entry.suffix.lower() in {".yaml", ".yml"}:
                    statement = select(JobRun).where(JobRun.playbook == rel_path).order_by(desc(JobRun.start_time)).limit(1)
                    run = self.db.exec(statement).first()
                    items.append({
                        "type": "file", 
                        "name": entry.stem, 
                        "path": rel_path, 
                        "status": run.status if run else None
                    })
            return items
        return build_tree(settings.PLAYBOOKS_DIR)

    def get_playbook_content(self, name: str) -> Optional[str]:
        file_path = self._validate_path(name)
        if not file_path or not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    def save_playbook_content(self, name: str, content: str) -> bool:
        file_path = self._validate_path(name)
        if not file_path: return False
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return True
        except OSError: return False

    def create_playbook(self, name: str) -> bool:
        if not name.endswith((".yaml", ".yml")): name += ".yaml"
        file_path = self._validate_path(name)
        if not file_path or file_path.exists(): return False
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("---\n- name: New Playbook\n  hosts: localhost\n  tasks:\n    - debug:\n        msg: 'Hello World'\n", encoding="utf-8")
            return True
        except OSError: return False

    def delete_playbook(self, name: str) -> bool:
        file_path = self._validate_path(name)
        if not file_path or not file_path.exists(): return False
        try:
            file_path.unlink()
            return True
        except OSError: return False

    def has_requirements(self, name: str) -> bool:
        file_path = self._validate_path(name)
        if not file_path: return False
        parent = file_path.parent
        return (parent / "requirements.yml").exists() or (parent / "requirements.yaml").exists()
