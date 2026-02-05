from pathlib import Path
from typing import List, Optional, Dict
import os
import re
import shutil
import sys
import asyncio
from datetime import datetime
from sqlmodel import Session, select, desc
from app.database import engine
from app.models import JobRun, EnvVar

PLAYBOOKS_DIR = Path("playbooks")

class PlaybookService:
    @staticmethod
    def _validate_path(name: str) -> Optional[Path]:
        if not re.match(r'^[a-zA-Z0-9_\-\.\/]+$', name):
            return None
        if not name.endswith((".yaml", ".yml")):
            return None
        try:
            target_path = (PLAYBOOKS_DIR / name).resolve()
            if not str(target_path).startswith(str(PLAYBOOKS_DIR.resolve())):
                return None
            return target_path
        except Exception:
            return None

    @staticmethod
    def list_playbooks() -> List[dict]:
        if not PLAYBOOKS_DIR.exists():
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            return []
            
        def build_tree(current_path: Path, relative_root: Path = PLAYBOOKS_DIR) -> List[dict]:
            items = []
            entries = sorted(list(current_path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            
            with Session(engine) as session:
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
                        run = session.exec(statement).first()
                        items.append({
                            "type": "file", 
                            "name": entry.name, 
                            "path": rel_path, 
                            "status": run.status if run else None
                        })
            return items
        return build_tree(PLAYBOOKS_DIR)

    @staticmethod
    def get_playbook_content(name: str) -> Optional[str]:
        file_path = PlaybookService._validate_path(name)
        if not file_path or not file_path.exists():
            return None
        return file_path.read_text(encoding="utf-8")

    @staticmethod
    def save_playbook_content(name: str, content: str) -> bool:
        file_path = PlaybookService._validate_path(name)
        if not file_path: return False
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return True
        except OSError: return False

    @staticmethod
    def create_playbook(name: str) -> bool:
        if not name.endswith((".yaml", ".yml")): name += ".yaml"
        file_path = PlaybookService._validate_path(name)
        if not file_path or file_path.exists(): return False
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("---\n- name: New Playbook\n  hosts: localhost\n  tasks:\n    - debug:\n        msg: 'Hello World'\n", encoding="utf-8")
            return True
        except OSError: return False

    @staticmethod
    def delete_playbook(name: str) -> bool:
        file_path = PlaybookService._validate_path(name)
        if not file_path or not file_path.exists(): return False
        try:
            file_path.unlink()
            return True
        except OSError: return False

    @staticmethod
    def has_requirements(name: str) -> bool:
        file_path = PlaybookService._validate_path(name)
        if not file_path: return False
        parent = file_path.parent
        return (parent / "requirements.yml").exists() or (parent / "requirements.yaml").exists()

class RunnerService:
    _locks: Dict[str, asyncio.Lock] = {}
    _processes: Dict[str, asyncio.subprocess.Process] = {}

    @staticmethod
    def _get_lock(playbook_name: str) -> asyncio.Lock:
        if playbook_name not in RunnerService._locks:
            RunnerService._locks[playbook_name] = asyncio.Lock()
        return RunnerService._locks[playbook_name]

    @staticmethod
    def _get_ansible_command(playbook_path: Path, check_mode: bool = False, env_vars: dict = None):
        """
        Helper to construct the ansible-playbook command.
        Returns: (cmd_list, error_message)
        """
        ansible_bin = shutil.which("ansible-playbook")
        inventory_file = "inventory.ini"
        
        # 1. Try native host execution
        if ansible_bin:
            cmd = [ansible_bin, str(playbook_path), "-i", inventory_file]
            if check_mode: cmd.append("--check")
            return cmd, None
            
        # 2. Try WSL if on Windows
        if sys.platform == "win32":
            wsl_bin = shutil.which("wsl")
            if wsl_bin:
                def to_wsl_path(path: Path) -> str:
                    abs_p = path.resolve()
                    drive = abs_p.drive.strip(':').lower()
                    parts = list(abs_p.parts[1:])
                    return f"/mnt/{drive}/" + "/".join(parts)

                wsl_playbook_path = to_wsl_path(playbook_path)
                wsl_inventory_path = to_wsl_path(Path(inventory_file))
                
                env_prefix = ""
                if env_vars:
                    for k, v in env_vars.items():
                        # Inject key environment variables into the shell command for WSL
                        if k.startswith(("ANSIBLE_", "SIB_")) or len(str(v)) < 100:
                             safe_v = str(v).replace("'", "'\\''")
                             env_prefix += f"{k}='{safe_v}' "
                
                # Construct bash command to properly set env vars and run ansible-playbook
                bash_cmd = f"{env_prefix}ansible-playbook '{wsl_playbook_path}' -i '{wsl_inventory_path}'"
                if check_mode: bash_cmd += " --check"
                
                res = [wsl_bin, "bash", "-c", bash_cmd]
                print(f"DEBUG: Constructing WSL command: {res}")
                return res, None
                
            return None, '<div class="log-error">Error: Ansible not found and WSL not available.</div>'
            
        return None, '<div class="log-error">Error: ansible-playbook executable not found in PATH.</div>'

    @staticmethod
    def format_log_line(line: str) -> str:
        css_class = ""
        if "TASK [" in line or "PLAY [" in line or "PLAY RECAP" in line: css_class = "log-meta"
        elif "ok: [" in line or "ok=" in line: css_class = "log-success"
        elif "changed: [" in line or "changed=" in line: css_class = "log-changed"
        elif "fatal:" in line or "failed=" in line or "unreachable=" in line: css_class = "log-error"
        elif "skipping:" in line: css_class = "log-debug"
        return f'<div class="{css_class}">{line}</div>' if css_class else f'<div>{line}</div>'

    @staticmethod
    async def run_playbook_headless(playbook_name: str, check_mode: bool = False) -> dict:
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
                job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                session.add(job); session.commit()
            return {'success': False, 'output': msg, 'rc': 1}

        # Resolve Env Vars
        with Session(engine) as session:
            env_vars_db = session.exec(select(EnvVar)).all()
        custom_env = {ev.key: ev.value for ev in env_vars_db}
        custom_env.update({"ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOWS": "1"})

        cmd, error_msg = RunnerService._get_ansible_command(playbook_path, env_vars=custom_env)
        if not cmd:
            with Session(engine) as session:
                job = session.get(JobRun, job_id)
                job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = error_msg; job.exit_code = 127
                session.add(job); session.commit()
            return {'success': False, 'output': error_msg, 'rc': 127}

        env = os.environ.copy(); env.update(custom_env)
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
                job.log_output = "\n".join([RunnerService.format_log_line(line) for line in output.splitlines()])
                job.exit_code = process.returncode
                session.add(job); session.commit()
                # Send notification while session is open/obj attached, or just use the status string
                status_str = job.status
            
            NotificationService.send_playbook_notification(playbook_name, status_str)
            return {'success': process.returncode == 0, 'output': output, 'rc': process.returncode}
        except Exception as e:
            msg = str(e)
            with Session(engine) as session:
                job = session.get(JobRun, job_id); job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                session.add(job); session.commit()
            return {'success': False, 'output': msg, 'rc': 1}

    @staticmethod
    def stop_playbook(playbook_name: str) -> bool:
        """
        Terminates the running process for the given playbook.
        """
        playbook_name = playbook_name.replace("\\", "/")
        process = RunnerService._processes.get(playbook_name)
        if process:
            # Terminate the process (SIGTERM)
            try:
                process.terminate()
                return True
            except ProcessLookupError:
                return False
        return False

    @staticmethod
    async def run_playbook(playbook_name: str, check_mode: bool = False):
        playbook_name = playbook_name.replace("\\", "/")
        trigger = "manual" if not check_mode else "manual_check"
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger)
        with Session(engine) as session:
            session.add(job); session.commit(); session.refresh(job); job_id = job.id
            
        log_buffer = []
        lock = RunnerService._get_lock(playbook_name)
        if lock.locked():
            msg = f'<div class="log-error">Error: Playbook {playbook_name} is already running.</div>'
            yield msg
            with Session(engine) as session:
                job = session.get(JobRun, job_id); job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                session.add(job); session.commit()
            return

        async with lock:
            playbook_path = PLAYBOOKS_DIR / playbook_name
            if not playbook_path.exists():
                msg = f'<div class="log-error">Error: Playbook {playbook_name} not found.</div>'
                yield msg
                with Session(engine) as session:
                    job = session.get(JobRun, job_id); job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                    session.add(job); session.commit()
                return

            if "mock" in playbook_name.lower():
                 yield f'<div class="log-meta">Starting Mock Execution...</div>'
                 await asyncio.sleep(1)
                 yield f'<div class="log-success">Mock Process finished</div>'
                 return

            # Resolve Env Vars
            with Session(engine) as session:
                env_vars_db = session.exec(select(EnvVar)).all()
            custom_env = {ev.key: ev.value for ev in env_vars_db}
            custom_env.update({"ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOWS": "1"})

            cmd, error_msg = RunnerService._get_ansible_command(playbook_path, check_mode=check_mode, env_vars=custom_env)
            if not cmd:
                 yield error_msg
                 with Session(engine) as session:
                    job = session.get(JobRun, job_id); job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = error_msg; job.exit_code = 127
                    session.add(job); session.commit()
                 return

            try:
                env = os.environ.copy(); env.update(custom_env)
                print(f"DEBUG: Executing command: {cmd}")
                process = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.STDOUT, 
                    env=env
                )
                # Register process for cancellation
                RunnerService._processes[playbook_name] = process
                
                if check_mode:
                    yield '<div class="log-changed" style="font-weight: bold; padding: 10px; border: 1px dashed #fbbf24; margin-bottom: 10px;">⚠️ DRY RUN MODE: No changes will be applied.</div>'
                
                msg = f'<div class="log-meta">Sible: Starting execution of {playbook_name}...</div>'
                yield msg; log_buffer.append(msg)
                
                while True:
                    line = await process.stdout.readline()
                    if not line: break
                    formatted_line = RunnerService.format_log_line(line.decode('utf-8', errors='replace').rstrip())
                    log_buffer.append(formatted_line); yield formatted_line
                
                await process.wait()
                exit_class = "log-success" if process.returncode == 0 else "log-error"
                yield f'<div class="{exit_class}">Sible: Process finished with exit code {process.returncode}</div>'
                
                with Session(engine) as session:
                    job = session.get(JobRun, job_id); job.status = "success" if process.returncode == 0 else "failed"
                    job.end_time = datetime.utcnow(); job.log_output = "\n".join(log_buffer); job.exit_code = process.returncode
                    session.add(job); session.commit()
                    status_str = job.status
                
                NotificationService.send_playbook_notification(playbook_name, status_str)
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_msg = str(e) or type(e).__name__
                yield f'<div class="log-error">Sible Error: Failed to start process: {err_msg}</div>'
                with Session(engine) as session:
                    job = session.get(JobRun, job_id); job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = err_msg; job.exit_code = 1
                    session.add(job); session.commit()
            finally:
                # Cleanup process registration
                if playbook_name in RunnerService._processes:
                    del RunnerService._processes[playbook_name]

    @staticmethod
    async def install_requirements(playbook_name: str):
        file_path = PlaybookService._validate_path(playbook_name)
        if not file_path:
            yield '<div class="log-error">Error: Invalid playbook path</div>'; return
        parent = file_path.parent
        req_file = "requirements.yml" if (parent / "requirements.yml").exists() else "requirements.yaml" if (parent / "requirements.yaml").exists() else None
        if not req_file:
            yield '<div class="log-error">Error: No requirements.yml found in directory.</div>'; return

        ansible_galaxy = shutil.which("ansible-galaxy")
        if not ansible_galaxy and sys.platform == "win32":
            wsl_bin = shutil.which("wsl")
            if wsl_bin:
                def to_wsl_path(path: Path) -> str:
                    abs_p = path.resolve(); drive = abs_p.drive.strip(':').lower(); parts = list(abs_p.parts[1:])
                    return f"/mnt/{drive}/" + "/".join(parts)
                cmd = [wsl_bin, "bash", "-c", f"cd '{to_wsl_path(parent)}' && ansible-galaxy install -r '{req_file}' -p ./roles"]
            else:
                yield '<div class="log-error">Error: ansible-galaxy not found and WSL not available.</div>'; return
        elif not ansible_galaxy:
            yield '<div class="log-error">Error: ansible-galaxy not found in PATH.</div>'; return
        else:
            cmd = [ansible_galaxy, "install", "-r", req_file, "-p", "./roles"]
        
        try:
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=str(parent), env=os.environ.copy())
            yield '<div class="log-meta">Sible: Starting installation of roles via ansible-galaxy...</div>'
            while True:
                line = await process.stdout.readline()
                if not line: break
                yield RunnerService.format_log_line(line.decode('utf-8', errors='replace').rstrip())
            await process.wait()
            yield f'<div class="log-success">Sible: Installation finished with code {process.returncode}</div>'
        except Exception as e:
            yield f'<div class="log-error">Sible Error: {str(e)}</div>'


    @staticmethod
    def cleanup_started_jobs():
        """
        Called on server startup.
        Finds any jobs in 'running' state and marks them as 'failed'.
        """
        from sqlmodel import Session, select
        from app.database import engine
        from app.models import JobRun
        import datetime

        try:
            with Session(engine) as session:
                running_jobs = session.exec(select(JobRun).where(JobRun.status == "running")).all()
                count = len(running_jobs)
                if count > 0:
                    print(f"[RunnerService] Found {count} zombie jobs. Cleaning up...")
                    for job in running_jobs:
                        job.status = "failed"
                        # Append to log that it was interrupted
                        if job.log_output:
                            job.log_output += "\\n[SYSTEM] Job interrupted by server restart."
                        else:
                            job.log_output = "[SYSTEM] Job interrupted by server restart."
                        session.add(job)
                    session.commit()
                    print(f"[RunnerService] Cleaned up {count} zombie jobs.")
        except Exception as e:
            print(f"[RunnerService] Error cleaning up zombie jobs: {e}")

class LinterService:
    @staticmethod
    async def lint_playbook_content(content: str) -> list:
        import tempfile, json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
            tmp.write(content); tmp_path = tmp.name
        try:
            lint_bin = shutil.which("ansible-lint")
            if not lint_bin and sys.platform == "win32":
                wsl_bin = shutil.which("wsl")
                if wsl_bin:
                    abs_p = Path(tmp_path).resolve(); drive = abs_p.drive.strip(':').lower(); parts = list(abs_p.parts[1:])
                    proc = await asyncio.create_subprocess_exec(
                        wsl_bin, "bash", "-c", f"ansible-lint -f json -q '/mnt/{drive}/" + "/".join(parts) + "'", 
                        stdout=asyncio.subprocess.PIPE, 
                        stderr=asyncio.subprocess.PIPE
                    )
                else: return [{"row": 0, "text": "ansible-lint not found and WSL not available", "type": "error"}]
            elif not lint_bin: return [{"row": 0, "text": "ansible-lint not found in PATH", "type": "error"}]
            else: proc = await asyncio.create_subprocess_exec(lint_bin, "-f", "json", "-q", tmp_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            output = stdout.decode('utf-8')
            errors = []
            if output.strip():
                try:
                    for issue in json.loads(output):
                        loc = issue.get("location", {}); line_num = loc.get("positions", {}).get("begin", {}).get("line", 1) if "positions" in loc else loc.get("lines", {}).get("begin", 1)
                        errors.append({"row": line_num - 1, "text": f"{issue.get('check_name')}: {issue.get('description')}", "type": "warning" if issue.get("severity", "major") != "blocker" else "error"})
                except json.JSONDecodeError: pass
            return errors
        except Exception as e: return [{"row": 0, "text": f"Linter error: {str(e)}", "type": "error"}]
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

class SettingsService:
    @staticmethod
    def get_settings() -> "AppSettings":
        from app.models import AppSettings
        with Session(engine) as session:
            settings = session.get(AppSettings, 1)
            if not settings:
                settings = AppSettings(id=1); session.add(settings); session.commit(); session.refresh(settings)
            return settings

    @staticmethod
    def update_settings(data: dict) -> "AppSettings":
        from app.models import AppSettings
        with Session(engine) as session:
            settings = session.get(AppSettings, 1)
            if not settings: settings = AppSettings(id=1)
            for k, v in data.items():
                if hasattr(settings, k): setattr(settings, k, v)
            session.add(settings); session.commit(); session.refresh(settings)
            return settings

class NotificationService:
    @staticmethod
    def send_notification(message: str, title: str = "Sible Alert"):
        import apprise
        settings = SettingsService.get_settings()
        if not settings.apprise_url: return
        apobj = apprise.Apprise(); apobj.add(settings.apprise_url); apobj.notify(body=message, title=title)

    @staticmethod
    def send_playbook_notification(playbook_name: str, status: str):
        settings = SettingsService.get_settings()
        if (status == "success" and settings.notify_on_success) or (status == "failed" and settings.notify_on_failure):
            emoji = "✅" if status == "success" else "🚨"
            NotificationService.send_notification(f"{emoji} Playbook '{playbook_name}' finished with status: {status.upper()}", title=f"Sible: {playbook_name}")

class InventoryService:
    INVENTORY_FILE = Path("inventory.ini")
    @staticmethod
    def get_inventory_content() -> str:
        if not InventoryService.INVENTORY_FILE.exists():
            InventoryService.INVENTORY_FILE.write_text("[all]\nlocalhost ansible_connection=local\n", encoding="utf-8")
        return InventoryService.INVENTORY_FILE.read_text(encoding="utf-8")
    @staticmethod
    def save_inventory_content(content: str) -> bool:
        try: InventoryService.INVENTORY_FILE.write_text(content, encoding="utf-8"); return True
        except Exception: return False
    @staticmethod
    async def ping_all() -> str:
        if not InventoryService.INVENTORY_FILE.exists(): return "No inventory file found."
        ansible_bin = shutil.which("ansible")
        if not ansible_bin and sys.platform == "win32":
             wsl_bin = shutil.which("wsl")
             if wsl_bin:
                abs_p = InventoryService.INVENTORY_FILE.resolve(); drive = abs_p.drive.strip(':').lower(); parts = list(abs_p.parts[1:])
                wsl_path = f"/mnt/{drive}/" + "/".join(parts)
                cmd = [wsl_bin, "bash", "-c", f"ansible all -m ping -i '{wsl_path}'"]
             else: return "Ansible not found. If using Windows, please run Sible inside WSL or install Ansible locally."
        elif not ansible_bin: return "Ansible not found. Please install it to use ping."
        else: cmd = ["ansible", "all", "-m", "ping", "-i", str(InventoryService.INVENTORY_FILE)]
        try:
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=os.environ.copy())
            stdout, _ = await process.communicate()
            return stdout.decode('utf-8', errors='replace')
        except Exception as e: return f"Error running ping: {str(e)}"
