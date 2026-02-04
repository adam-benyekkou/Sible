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
        # 1. Allow alphanumeric, dashes, underscores, dots, AND slashes
        if not re.match(r'^[a-zA-Z0-9_\-\.\/]+$', name):
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
    def list_playbooks_flat() -> List[dict]:
        """
        Returns a flat list of all playbook files with their relative paths.
        """
        if not PLAYBOOKS_DIR.exists():
            return []
            
        from app.database import engine
        from app.models import JobRun
        from sqlmodel import Session, select, desc
        
        items = []
        # Walk through the directory
        for root, dirs, files in os.walk(PLAYBOOKS_DIR):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    full_path = Path(root) / file
                    rel_path = str(full_path.relative_to(PLAYBOOKS_DIR)).replace("\\", "/")
                    
                    with Session(engine) as session:
                        statement = select(JobRun).where(JobRun.playbook == rel_path).order_by(desc(JobRun.start_time)).limit(1)
                        run = session.exec(statement).first()
                        status = run.status if run else None
                        
                    items.append({
                        "name": rel_path, # Use relative path as name
                        "path": rel_path,
                        "status": status
                    })
        
        # Sort by name
        items.sort(key=lambda x: x['name'])
        return items

    @staticmethod
    def list_playbooks() -> List[dict]:
        """
        Scans the playbooks directory recursively and returns a tree structure.
        """
        if not PLAYBOOKS_DIR.exists():
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            return []
            
        from app.database import engine
        from app.models import JobRun
        from sqlmodel import Session, select, desc

        def build_tree(current_path: Path, relative_root: Path = PLAYBOOKS_DIR) -> List[dict]:
            items = []
            # Sort files and folders
            entries = sorted(list(current_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            
            with Session(engine) as session:
                for entry in entries:
                    rel_path = str(entry.relative_to(relative_root)).replace("\\", "/")
                    
                    if entry.is_dir():
                        children = build_tree(entry, relative_root)
                        if children: # Only show folders with content (or just show all)
                            items.append({
                                "type": "directory",
                                "name": entry.name,
                                "path": rel_path,
                                "children": children
                            })
                    elif entry.suffix.lower() in {".yaml", ".yml"}:
                        # Get Status for this specific path
                        statement = select(JobRun).where(JobRun.playbook == rel_path).order_by(desc(JobRun.start_time)).limit(1)
                        run = session.exec(statement).first()
                        status = run.status if run else None
                        
                        items.append({
                            "type": "file",
                            "name": entry.name,
                            "path": rel_path,
                            "status": status
                        })
            return items

        return build_tree(PLAYBOOKS_DIR)

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
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
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
            file_path.parent.mkdir(parents=True, exist_ok=True)
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

import shutil
import sys
import asyncio
import os
from sqlmodel import Session, select, desc
from app.database import engine
from app.models import JobRun
from datetime import datetime

from datetime import datetime
from typing import Dict, Optional

class RunnerService:
    _locks: Dict[str, asyncio.Lock] = {}

    @staticmethod
    def _get_lock(playbook_name: str) -> asyncio.Lock:
        if playbook_name not in RunnerService._locks:
            RunnerService._locks[playbook_name] = asyncio.Lock()
        return RunnerService._locks[playbook_name]

    @staticmethod
    def _get_ansible_command(playbook_path: Path, check_mode: bool = False):
        """
        Helper to construct the ansible-playbook command.
        Returns: (cmd_list, error_message)
        """
        # Check if ansible-playbook is installed
        ansible_bin = shutil.which("ansible-playbook")
        
        if ansible_bin:
            cmd = [ansible_bin, str(playbook_path)]
            if check_mode:
                cmd.append("--check")
            return cmd, None
        elif sys.platform == "win32":
            # Try via WSL
            wsl_bin = shutil.which("wsl")
            if wsl_bin:
                # Mock Mode logic moved to caller or handled here? 
                # For simplicity, keeping Mock logic in caller or distinct.
                return None, '<div class="log-changed">Ansible not found. (WSL detection incomplete)</div>'
            else:
                 return None, '<div class="log-error">Error: Ansible not found and WSL not available.</div>'
        else:
             return None, '<div class="log-error">Error: ansible-playbook executable not found in PATH.</div>'

    @staticmethod
    def format_log_line(line: str) -> str:
        """
        Applies CSS classes to a log line based on its content.
        """
        css_class = ""
        if "TASK [" in line or "PLAY [" in line or "PLAY RECAP" in line:
            css_class = "log-meta"
        elif "ok: [" in line or "ok=" in line:
            css_class = "log-success"
        elif "changed: [" in line or "changed=" in line:
            css_class = "log-changed"
        elif "fatal:" in line or "failed=" in line or "unreachable=" in line:
            css_class = "log-error"
        elif "skipping:" in line:
            css_class = "log-debug"
        
        if css_class:
            return f'<div class="{css_class}">{line}</div>'
        else:
            return f'<div>{line}</div>'

    @staticmethod
    async def run_playbook_headless(playbook_name: str, check_mode: bool = False) -> dict:
        """
        Runs a playbook in the background (headless) and returns the result.
        Returns: { 'success': bool, 'output': str, 'rc': int }
        """
        # Normalize path to forward slashes for DB consistency
        playbook_name = playbook_name.replace("\\", "/")
        trigger = "cron" if not check_mode else "manual_check"
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger)
        with Session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id

        playbook_path = PLAYBOOKS_DIR / playbook_name
        if not playbook_path.exists():
            msg = f"Playbook {playbook_name} not found"
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = msg
                job.exit_code = 1
                session.add(job)
                session.commit()
            return {'success': False, 'output': msg, 'rc': 1}

        # Mock Mode Hook for Testing
        if "mock" in playbook_name.lower() or "hello" in playbook_name.lower():
            # Real execution for hello.yaml too? Optional.
            # If user wants to see logs in history, we should probably record mock output too.
            # But let's stick to the existing logic + saving.
            pass # Continue to real logic if not purely mock return
            
        # Re-using previous Mock logic for fast returns if strictly "mock" string
        if "mock" in playbook_name.lower():
             await asyncio.sleep(2)
             msg = "Mock execution successful."
             formatted_msg = RunnerService.format_log_line(msg)
             with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "success"
                job.end_time = datetime.utcnow()
                job.log_output = formatted_msg
                job.exit_code = 0
                session.add(job)
                session.commit()
             return {'success': True, 'output': msg, 'rc': 0}

        cmd, error_msg = RunnerService._get_ansible_command(playbook_path)
        if not cmd:
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = error_msg
                job.exit_code = 127
                session.add(job)
                session.commit()
            return {'success': False, 'output': error_msg, 'rc': 127}


        env = os.environ.copy()
        env["ANSIBLE_FORCE_COLOR"] = "0"
        env["ANSIBLE_NOCOWS"] = "1"

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env
            )
            stdout, _ = await process.communicate()
            output = stdout.decode('utf-8', errors='replace')
            
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "success" if process.returncode == 0 else "failed"
                job.end_time = datetime.utcnow()
                # Apply formatting to all lines for headless
                formatted_output = "\n".join([RunnerService.format_log_line(line) for line in output.splitlines()])
                job.log_output = formatted_output
                job.exit_code = process.returncode
                session.add(job)
                session.commit()
            
            # Send Notification
            NotificationService.send_playbook_notification(playbook_name, "success" if process.returncode == 0 else "failed")
            
            return {
                'success': process.returncode == 0,
                'output': output,
                'rc': process.returncode
            }
        except Exception as e:
            msg = str(e)
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = msg
                job.exit_code = 1
                session.add(job)
                session.commit()
            return {'success': False, 'output': msg, 'rc': 1}

    @staticmethod
    async def run_playbook(playbook_name: str, check_mode: bool = False):
        """
        Runs an ansible-playbook and yields the output line by line.
        """
        # Normalize path to forward slashes for DB consistency
        playbook_name = playbook_name.replace("\\", "/")
        trigger = "manual" if not check_mode else "manual_check"
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger)
        with Session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id
            
        log_buffer = []

        # Lock Check
        lock = RunnerService._get_lock(playbook_name)
        if lock.locked():
            msg = f'<div class="log-error">Error: Playbook {playbook_name} is already running.</div>'
            yield msg
            # Mark failed in DB immediately? Or just skip logging?
            # Better to record the attempt failure.
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = msg
                job.exit_code = 1
                session.add(job)
                session.commit()
            return

        async with lock:
            playbook_path = PLAYBOOKS_DIR / playbook_name
        if not playbook_path.exists():
            msg = f'<div class="log-error">Error: Playbook {playbook_name} not found.</div>'
            yield msg
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = msg
                job.exit_code = 1
                session.add(job)
                session.commit()
            return

        # Mock Hook for UI
        if "mock" in playbook_name.lower():
             yield f'<div class="log-meta">Starting Mock Execution...</div>'
             await asyncio.sleep(1)
             # ... simplified mock ...
             yield f'<div class="log-success">Mock Process finished</div>'
             return

        cmd, error_msg = RunnerService._get_ansible_command(playbook_path)
        if not cmd:
             yield error_msg
             with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = error_msg
                job.exit_code = 127
                session.add(job)
                session.commit()
             return

        env = os.environ.copy()
        env["ANSIBLE_FORCE_COLOR"] = "0"
        env["ANSIBLE_NOCOWS"] = "1"

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env
            )

            if check_mode:
                yield '<div class="log-changed" style="font-weight: bold; padding: 10px; border: 1px dashed #fbbf24; margin-bottom: 10px;">⚠️ DRY RUN MODE: No changes will be applied.</div>'
            
            msg = f'<div class="log-meta">Sible: Starting execution of {playbook_name}...{" (Dry Run)" if check_mode else ""}</div>'
            yield msg
            log_buffer.append(f"Starting execution of {playbook_name}...")

            # Yield output as it comes
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                # Raw text for logs
                decoded_line_raw = line.decode('utf-8', errors='replace').rstrip()
                
                # HTML for Stream
                decoded_line = decoded_line_raw
                formatted_line = RunnerService.format_log_line(decoded_line)
                
                # Buffer the FORMATTED line for DB so history looks same as stream
                log_buffer.append(formatted_line)
                
                yield formatted_line

            await process.wait()
            
            exit_class = "log-success" if process.returncode == 0 else "log-error"
            yield f'<div class="{exit_class}">Sible: Process finished with exit code {process.returncode}</div>'
            
            # DB: Save logs
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "success" if process.returncode == 0 else "failed"
                job.end_time = datetime.utcnow()
                job.log_output = "\n".join(log_buffer)
                job.exit_code = process.returncode
                session.add(job)
                session.commit()

            # Send Notification
            NotificationService.send_playbook_notification(playbook_name, "success" if process.returncode == 0 else "failed")
        
        except Exception as e:
            err_msg = str(e)
            yield f'<div class="log-error">Sible Error: Failed to start process: {err_msg}</div>'
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"
                job.end_time = datetime.utcnow()
                job.log_output = err_msg
                job.exit_code = 1
                session.add(job)
                session.commit()

class LinterService:
    @staticmethod
    async def lint_playbook_content(content: str) -> list:
        """
        Lints the provided playbook content using ansible-lint.
        Returns a list of dicts: {line, message, severity, rule}
        """
        import tempfile
        import json
        
        # Write content to temp file
        # We use a specific suffix so ansible-lint knows it's yaml
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            
        try:
            # Run ansible-lint
            # -f json: Output as JSON
            # -q: Quiet
            proc = await asyncio.create_subprocess_exec(
                "ansible-lint", "-f", "json", "-q", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            output = stdout.decode('utf-8')
            errors = []
            
            if output.strip():
                try:
                    lint_results = json.loads(output)
                    for issue in lint_results:
                        # Extract relevant fields
                        # ansible-lint json format (varies by version, v6+ uses positions): 
                        # {"location": {"positions": {"begin": {"line": 8 ...}}}}
                        
                        location = issue.get("location", {})
                        line_num = 1
                        
                        # Try v6+ format
                        if "positions" in location:
                            line_num = location["positions"].get("begin", {}).get("line", 1)
                        # Try older format
                        elif "lines" in location:
                            line_num = location["lines"].get("begin", 1)
                            
                        errors.append({
                            "row": line_num - 1, # Ace is 0-indexed
                            "text": f"{issue.get('check_name')}: {issue.get('description')}",
                            "type": "warning" if issue.get("severity", "major") != "blocker" else "error"
                        })
                except json.JSONDecodeError:
                    # Fallback if not valid JSON (e.g. error message)
                    pass
            
            return errors
            
        except Exception as e:
            return [{"row": 0, "text": f"Linter error: {str(e)}", "type": "error"}]
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class SettingsService:
    @staticmethod
    def get_settings() -> "AppSettings":
        from app.models import AppSettings
        with Session(engine) as session:
            settings = session.get(AppSettings, 1)
            if not settings:
                settings = AppSettings(id=1)
                session.add(settings)
                session.commit()
                session.refresh(settings)
            return settings

    @staticmethod
    def update_settings(data: dict) -> "AppSettings":
        from app.models import AppSettings
        with Session(engine) as session:
            settings = session.get(AppSettings, 1)
            if not settings:
                settings = AppSettings(id=1)
            
            for key, value in data.items():
                if hasattr(settings, key):
                    # Check box conversion if needed (but routes handle it)
                    setattr(settings, key, value)
            
            session.add(settings)
            session.commit()
            session.refresh(settings)
            return settings

class NotificationService:
    @staticmethod
    def send_notification(message: str, title: str = "Sible Alert"):
        import apprise
        settings = SettingsService.get_settings()
        if not settings.apprise_url:
            return
        
        apobj = apprise.Apprise()
        apobj.add(settings.apprise_url)
        apobj.notify(
            body=message,
            title=title,
        )

    @staticmethod
    def send_playbook_notification(playbook_name: str, status: str):
        settings = SettingsService.get_settings()
        
        should_notify = False
        if status == "success" and settings.notify_on_success:
            should_notify = True
        elif status == "failed" and settings.notify_on_failure:
            should_notify = True
            
        if should_notify:
            emoji = "✅" if status == "success" else "🚨"
            message = f"{emoji} Playbook '{playbook_name}' finished with status: {status.upper()}"
            NotificationService.send_notification(message, title=f"Sible: {playbook_name}")
