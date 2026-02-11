from pathlib import Path
from typing import List, Optional, Any
from sqlmodel import Session, select, desc
import re
import yaml
from app.core.config import get_settings
from app.models import JobRun, FavoritePlaybook
from datetime import datetime
import os

settings = get_settings()

class PlaybookService:
    """Manages Ansible playbook files, metadata, and directory structures.

    This service handles filesystem operations for playbooks, extracts
    metadata (descriptions, variables), and manages user favorites and
    execution history snapshots for the UI.
    """
    def __init__(self, db: Session):
        """Initializes the service.

        Args:
            db: Database session for metadata and history queries.
        """
        self.db = db

    @property
    def base_dir(self) -> Path:
        """Resolves the physical root directory for all playbooks.

        Why: Sible supports configurable playbook locations. This property
        ensures all filesystem operations are relative to the user's
        workspace setting.

        Returns:
            Path object pointing to the playbooks root.
        """
        from app.models import AppSettings
        db_settings = self.db.get(AppSettings, 1)
        path_str = db_settings.playbooks_path if db_settings else "/app/playbooks"
        return Path(path_str)

    def _validate_path(self, name: str) -> Optional[Path]:
        """Validates a playbook path to prevent directory traversal attacks.

        Why: Since playbooks are stored on the filesystem, we must ensure
        that user-provided names don't escape the base directory using '../'
        or absolute paths.

        Args:
            name: The relative path to the playbook.

        Returns:
            Resolved absolute Path if valid and safe, else None.
        """
        if not re.match(r'^[a-zA-Z0-9_\-\.\/ ]+$', name):
            return None
        if not name.endswith((".yaml", ".yml")):
            return None
        try:
            base = self.base_dir.resolve()
            target_path = (base / name).resolve()
            # Ensure the resolved path is within the base directory
            if not os.path.commonpath([str(base), str(target_path)]) == str(base):
                return None
            return target_path
        except Exception:
            return None

    def list_playbooks(self) -> list[dict[str, Any]]:
        """Generates a recursive tree structure of the playbooks directory.

        Why: Powers the sidebar file browser, allowing users to navigate
        nested playbook structures.

        Returns:
            A nested list structure suitable for tree-view rendering.
        """
        base = self.base_dir
        if not base.exists():
            base.mkdir(parents=True, exist_ok=True)
            return []
            
        def build_tree(current_path: Path, relative_root: Path) -> List[dict]:
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
        return build_tree(base, base)

    def get_playbook_content(self, name: str) -> Optional[str]:
        """Reads the raw content of a playbook file.

        Args:
            name: Relative path to the playbook.

        Returns:
            File content as string, or None if invalid/missing.
        """
        file_path = self._validate_path(name)
        if not file_path or not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    def save_playbook_content(self, name: str, content: str) -> bool:
        """Overwrites a playbook file with new content.

        Args:
            name: Relative path to the playbook.
            content: New YAML content.

        Returns:
            True if successful, False otherwise.
        """
        file_path = self._validate_path(name)
        if not file_path: return False
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return True
        except OSError: return False

    def create_playbook(self, name: str) -> bool:
        """Initializes a new playbook file with a boilerplate template.

        Args:
            name: Desired relative path (with or without extension).

        Returns:
            True if created, False if already exists or path invalid.
        """
        if not name.endswith((".yaml", ".yml")): name += ".yaml"
        file_path = self._validate_path(name)
        if not file_path or file_path.exists(): return False
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("---\n- name: New Playbook\n  hosts: localhost\n  tasks:\n    - debug:\n        msg: 'Hello World'\n", encoding="utf-8")
            return True
        except OSError: return False

    def delete_playbook(self, name: str) -> bool:
        """Deletes a playbook file from disk.

        Args:
            name: Relative path to the playbook.

        Returns:
            True if deleted, False otherwise.
        """
        file_path = self._validate_path(name)
        if not file_path or not file_path.exists(): return False
        try:
            file_path.unlink()
            return True
        except OSError: return False

    def get_playbooks_metadata(
        self, 
        search: Optional[str] = None, 
        user_id: Optional[int] = None, 
        limit: int = 20, 
        offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieves an enriched list of playbooks with history and favorites.

        Why: Powers the Dashboard/Template Library view. It combines
        filesystem data with database history to show who ran what and when.

        Args:
            search: Fuzzy filter for name/description.
            user_id: Current user ID for resolving favorite status.
            limit: Page size.
            offset: Page offset.

        Returns:
            A tuple of (metadata_list, total_filtered_count).
        """
        base = self.base_dir
        if not base.exists():
            return [], 0
            
        # Fetch user favorites if user_id is provided
        favorites = set()
        if user_id:
            fav_objs = self.db.exec(
                select(FavoritePlaybook).where(FavoritePlaybook.user_id == user_id)
            ).all()
            favorites = {f.playbook_path for f in fav_objs}

        playbooks = []
        for file_path in base.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in {".yaml", ".yml"}:
                rel_path = str(file_path.relative_to(base)).replace("\\", "/")
                content = self.get_playbook_content(rel_path) or ""
                description = self._extract_description(content)
                
                # Search filtering
                if search:
                    s = search.lower()
                    if s not in rel_path.lower() and s not in file_path.stem.lower() and s not in description.lower():
                        continue

                # Fetch history metadata
                # Use subquery or separate query for latest job per playbook?
                # For simplicity and performance with small sets, we'll get last successful/failed run
                last_job = self.db.exec(
                    select(JobRun)
                    .where(JobRun.playbook == rel_path)
                    .order_by(desc(JobRun.start_time))
                ).first()

                mtime = file_path.stat().st_mtime
                last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                
                # Folder prefix
                folder_parts = rel_path.split("/")
                folder_prefix = " / ".join(folder_parts[:-1]) if len(folder_parts) > 1 else ""

                duration = self._format_duration(last_job) if last_job else ""

                playbooks.append({
                    "name": file_path.stem,
                    "path": rel_path,
                    "folder": folder_prefix,
                    "description": description,
                    "last_modified": last_modified,
                    "status": last_job.status if last_job else "never_run",
                    "last_run": self._get_relative_time(last_job.start_time) if last_job else "Never executed",
                    "duration": duration,
                    "last_job_id": last_job.id if last_job else None,
                    "author": last_job.username if last_job and last_job.username else "System",
                    "is_favorited": rel_path in favorites
                })
        
        # Sort
        sorted_playbooks = sorted(playbooks, key=lambda x: x["name"].lower())
        total_count = len(sorted_playbooks)
        
        # Paginate
        paginated_playbooks = sorted_playbooks[offset : offset + limit]
        
        return paginated_playbooks, total_count

    def toggle_favorite(self, playbook_path: str, user_id: int) -> bool:
        """Toggles favorite status. Returns True if now favorited, False if removed."""
        existing = self.db.exec(
            select(FavoritePlaybook)
            .where(FavoritePlaybook.user_id == user_id)
            .where(FavoritePlaybook.playbook_path == playbook_path)
        ).first()

        if existing:
            self.db.delete(existing)
            self.db.commit()
            return False
        else:
            new_fav = FavoritePlaybook(user_id=user_id, playbook_path=playbook_path)
            self.db.add(new_fav)
            self.db.commit()
            return True

    def _format_duration(self, job: JobRun) -> str:
        if job.status == "running":
            return "Running..."
        if not job.end_time:
            return ""
        
        diff = job.end_time - job.start_time
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        rem_seconds = seconds % 60
        if minutes < 60:
            return f"{minutes}m {rem_seconds}s"
        hours = minutes // 60
        rem_minutes = minutes % 60
        return f"{hours}h {rem_minutes}m"

    def _get_relative_time(self, dt: datetime) -> str:
        diff = datetime.utcnow() - dt
        if diff.days > 0:
            if diff.days == 1: return "Yesterday"
            if diff.days < 7: return f"{diff.days} days ago"
            return dt.strftime("%Y-%m-%d")
        
        seconds = diff.seconds
        if seconds < 60: return "Just now"
        if seconds < 3600: return f"{seconds // 60} minutes ago"
        return f"{seconds // 3600} hours ago"

    def _extract_description(self, content: str) -> str:
        # Look for # Description: ... or # description: ...
        match = re.search(r'^#\s*Description:\s*(.*)$', content, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Infrastructure playbook"

    def delete_playbooks_bulk(self, names: List[str]) -> bool:
        success = True
        for name in names:
            if not self.delete_playbook(name):
                success = False
        return success

    def has_requirements(self, name: str) -> bool:
        file_path = self._validate_path(name)
        if not file_path: return False
        parent = file_path.parent
        return (parent / "requirements.yml").exists() or (parent / "requirements.yaml").exists()

    def get_playbook_variables(self, name: str) -> list[str]:
        """Detects required input variables by parsing prompts and templates.

        Why: Sible displays a dynamic form before execution. This method
        finds custom variables within the YAML (vars_prompt) and Jinja2
        expressions ({{ var }}) so the user can provide values.

        Args:
            name: Relative path to the playbook.

        Returns:
            Sorted list of unique variable names.
        """
        content = self.get_playbook_content(name)
        if not content: return []
        
        variables = set()
        
        # 1. Parse vars_prompt
        try:
            data = yaml.safe_load(content)
            if isinstance(data, list):
                for play in data:
                    if 'vars_prompt' in play:
                        for prompt in play['vars_prompt']:
                            if isinstance(prompt, dict) and 'name' in prompt:
                                variables.add(prompt['name'])
                            elif isinstance(prompt, str):
                                variables.add(prompt)
        except Exception:
            pass # Fallback to regex if YAML parsing fails or is incomplete
            
        # 2. Regex for {{ var }}
        # Matches {{ var_name }} or {{ var_name | filter }}
        # Excludes standard ansible vars (item, ansible_*, etc.)
        regex = r'\{\{\s*([a-zA-Z0-9_]+)(?:\s*\|.*?)?\s*\}\}'
        matches = re.findall(regex, content)
        
        ignored_vars = {
            'item', 'playbook_dir', 'inventory_hostname', 'ansible_host', 
            'ansible_user', 'ansible_port', 'ansible_connection', 'groups',
            'group_names', 'hostvars'
        }
        
        for var in matches:
            if var not in ignored_vars and not var.startswith('ansible_'):
                variables.add(var)
                
        return sorted(list(variables))
