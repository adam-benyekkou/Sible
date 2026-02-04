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
    def list_playbooks() -> List[dict]:
        """
        Scans the playbooks directory and returns a list of files with status.
        Returns: [{"name": "foo.yaml", "status": "success"}, ...]
        """
        if not PLAYBOOKS_DIR.exists():
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            return []
            
        extensions = {".yaml", ".yml"}
        playbooks = [
            f.name for f in PLAYBOOKS_DIR.iterdir() 
            if f.is_file() and f.suffix.lower() in extensions
        ]
        
        playbooks_data = []
        # Lazy import to simplify - or we updated the main import below. 
        # But PlaybookService is above the imports.
        # Wait, the imports are at line 119? 
        # Ah, SERVICES.PY HAS IMPORTS IN THE MIDDLE? 
        # Checking file content... yes: line 119 `from sqlmodel import ...`
        # PlaybookService is defined ABOVE those imports? 
        # The file content shows PlaybookService lines 8-114.
        # Imports start at 115.
        # This means PlaybookService CANNOT use `Session` or `JobRun` if they are imported below it?
        # Unless they are imported at top?
        # Top imports: `from pathlib import Path`, etc.
        # The imports at 119 seem to be for RunnerService.
        # If I want to use DB in PlaybookService, I must move imports up or import locally.
        
        from app.database import engine
        from app.models import JobRun
        from sqlmodel import Session, select, desc

        with Session(engine) as session:
             for name in sorted(playbooks):
                statement = select(JobRun).where(JobRun.playbook == name).order_by(desc(JobRun.start_time)).limit(1)
                run = session.exec(statement).first()
                status = run.status if run else None
                playbooks_data.append({"name": name, "status": status})
                
        return playbooks_data

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
        # DB: Start Run
        # DB: Start Run
        trigger = "cron" if notPB_check_mode else "manual_check"
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
        # DB: Start Run
        # DB: Start Run
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
