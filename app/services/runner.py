from pathlib import Path
from typing import Dict, Tuple, List
import os
import shutil
import sys
import asyncio
from datetime import datetime
from sqlmodel import Session, select
from app.models import JobRun, EnvVar
from app.config import get_settings
from app.services.notification import NotificationService

settings = get_settings()

class RunnerService:
    _locks: Dict[str, asyncio.Lock] = {}
    _processes: Dict[str, asyncio.subprocess.Process] = {}

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    def _get_lock(self, playbook_name: str) -> asyncio.Lock:
        if playbook_name not in RunnerService._locks:
            RunnerService._locks[playbook_name] = asyncio.Lock()
        return RunnerService._locks[playbook_name]

    @staticmethod
    def _get_ansible_command(
        playbook_path: Path, 
        check_mode: bool = False, 
        env_vars: dict = None, 
        galaxy: bool = False, 
        galaxy_req_file: str = None, 
        galaxy_cwd: Path = None,
        limit: str = None,
        tags: str = None,
        verbosity: int = 0,
        extra_vars: dict = None
    ) -> Tuple[List[str], str]:
        inventory_file = "inventory.ini"
        
        # 1. Try Docker execution if enabled
        if settings.USE_DOCKER:
            docker_bin = shutil.which("docker")
            if docker_bin:
                # Docker on Windows needs paths handled carefully for mounting
                # We mount PLAYBOOKS_DIR to DOCKER_WORKSPACE_PATH
                # If we are running in Docker, we need the host's playbooks path for volume mounting
                if settings.HOST_WORKSPACE_PATH:
                    host_workdir = f"{settings.HOST_WORKSPACE_PATH}/playbooks"
                else:
                    host_workdir = str(settings.PLAYBOOKS_DIR.resolve())
                
                container_workdir = settings.DOCKER_WORKSPACE_PATH
                
                # Command within container
                if galaxy:
                    inner_cmd = f"cd '{container_workdir}' && ansible-galaxy install -r '{galaxy_req_file}' -p ./roles"
                else:
                    # Resolve relative path of playbook from PLAYBOOKS_DIR
                    try:
                        rel_playbook = playbook_path.resolve().relative_to(settings.PLAYBOOKS_DIR.resolve())
                        container_playbook_path = f"{container_workdir}/{rel_playbook.as_posix()}"
                    except ValueError:
                         container_playbook_path = f"{container_workdir}/{playbook_path.name}"
                    
                    inner_cmd = f"ansible-playbook '{container_playbook_path}' -i '{container_workdir}/{inventory_file}'"
                    if check_mode: inner_cmd += " --check"
                    if limit: inner_cmd += f" --limit '{limit}'"
                    if tags: inner_cmd += f" --tags '{tags}'"
                    if verbosity > 0: inner_cmd += f" -{'v' * verbosity}"
                    if extra_vars:
                        import json
                        ev_json = json.dumps(extra_vars)
                        inner_cmd += f" -e '{ev_json}'"
 
                cmd = [
                    docker_bin, "run", "--rm",
                    "-v", f"{host_workdir}:{container_workdir}",
                    "-w", container_workdir
                ]
                
                # Add environment variables
                if env_vars:
                    for k, v in env_vars.items():
                        cmd.extend(["-e", f"{k}={v}"])
                
                cmd.append(settings.DOCKER_IMAGE)
                cmd.extend(["sh", "-c", inner_cmd])
                
                print(f"DEBUG: Constructing Docker command: {cmd}")
                return cmd, None
 
        # 2. Try native host execution as fallback
        ansible_bin = shutil.which("ansible-playbook" if not galaxy else "ansible-galaxy")
        if ansible_bin:
            if galaxy:
                 cmd = [ansible_bin, "install", "-r", galaxy_req_file, "-p", "./roles"]
            else:
                 cmd = [ansible_bin, str(playbook_path), "-i", inventory_file]
                 if check_mode: cmd.append("--check")
                 if limit: cmd.extend(["--limit", limit])
                 if tags: cmd.extend(["--tags", tags])
                 if verbosity > 0: cmd.append(f"-{'v' * verbosity}")
                 if extra_vars:
                     import json
                     cmd.extend(["-e", json.dumps(extra_vars)])
            return cmd, None
            
        # 3. Try WSL if on Windows as final fallback
        if sys.platform == "win32":
            wsl_bin = shutil.which("wsl")
            if wsl_bin:
                def to_wsl_path(path: Path) -> str:
                    abs_p = path.resolve()
                    drive = abs_p.drive.strip(':').lower()
                    parts = list(abs_p.parts[1:])
                    return f"/mnt/{drive}/" + "/".join(parts)
 
                if galaxy:
                     wsl_cwd = to_wsl_path(galaxy_cwd)
                     bash_cmd = f"cd '{wsl_cwd}' && ansible-galaxy install -r '{galaxy_req_file}' -p ./roles"
                else:
                    wsl_playbook_path = to_wsl_path(playbook_path)
                    wsl_inventory_path = to_wsl_path(settings.PLAYBOOKS_DIR / inventory_file)
                    
                    env_prefix = ""
                    if env_vars:
                        for k, v in env_vars.items():
                            if k.startswith(("ANSIBLE_", "SIB_")) or len(str(v)) < 100:
                                 safe_v = str(v).replace("'", "'\\''")
                                 env_prefix += f"{k}='{safe_v}' "
                    
                    bash_cmd = f"{env_prefix}ansible-playbook '{wsl_playbook_path}' -i '{wsl_inventory_path}'"
                    if check_mode: bash_cmd += " --check"
                    if limit: bash_cmd += f" --limit '{limit}'"
                    if tags: bash_cmd += f" --tags '{tags}'"
                    if verbosity > 0: bash_cmd += f" -{'v' * verbosity}"
                    if extra_vars:
                        import json
                        ev_json = json.dumps(extra_vars).replace("'", "'\\''")
                        bash_cmd += f" -e '{ev_json}'"
                
                res = [wsl_bin, "bash", "-c", bash_cmd]
                return res, None
                
            return None, '<div class="log-error">Error: Ansible not found (Docker/Host/WSL).</div>'
            
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
 
    async def run_playbook_headless(self, playbook_name: str, check_mode: bool = False, limit: str = None, tags: str = None, verbosity: int = 0, extra_vars: dict = None) -> dict:
        playbook_name = playbook_name.replace("\\", "/")
        trigger = "cron" if not check_mode else "manual_check"
        
        # Create job record with params
        import json
        params_dict = {
            "limit": limit,
            "tags": tags,
            "verbosity": verbosity,
            "extra_vars": extra_vars
        }
        db_params = json.dumps(params_dict) if any(v is not None and v != "" and v != {} and v != 0 for v in params_dict.values()) else None
        
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger, params=db_params)
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        job_id = job.id
 
        playbook_path = settings.PLAYBOOKS_DIR / playbook_name
        if not playbook_path.exists():
            msg = f"Playbook {playbook_name} not found"
            job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
            self.db.add(job); self.db.commit()
            return {'success': False, 'output': msg, 'rc': 1}
 
        env_vars_db = self.db.exec(select(EnvVar)).all()
        custom_env = {ev.key: ev.value for ev in env_vars_db}
        custom_env.update({"ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOWS": "1"})
 
        cmd, error_msg = self._get_ansible_command(
            playbook_path, 
            check_mode=check_mode,
            env_vars=custom_env,
            limit=limit,
            tags=tags,
            verbosity=verbosity,
            extra_vars=extra_vars
        )
        if not cmd:
            job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = error_msg; job.exit_code = 127
            self.db.add(job); self.db.commit()
            return {'success': False, 'output': error_msg, 'rc': 127}
 
        env = os.environ.copy()
        env.update(custom_env)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT, 
                env=env
            )
            stdout, _ = await process.communicate()
            output = stdout.decode('utf-8', errors='replace')
            
            job.status = "success" if process.returncode == 0 else "failed"
            job.end_time = datetime.utcnow()
            job.log_output = "\n".join([self.format_log_line(line) for line in output.splitlines()])
            job.exit_code = process.returncode
            self.db.add(job); self.db.commit()
            
            self.notification_service.send_playbook_notification(playbook_name, job.status)
            return {'success': process.returncode == 0, 'output': output, 'rc': process.returncode}
        except Exception as e:
            msg = str(e)
            job = self.db.get(JobRun, job_id)
            if job:
                job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                self.db.add(job); self.db.commit()
            return {'success': False, 'output': msg, 'rc': 1}
 
    def stop_playbook(self, playbook_name: str) -> bool:
        playbook_name = playbook_name.replace("\\", "/")
        process = RunnerService._processes.get(playbook_name)
        if process:
            try:
                process.terminate()
                return True
            except ProcessLookupError:
                return False
        return False
 
    async def run_playbook(self, playbook_name: str, check_mode: bool = False, limit: str = None, tags: str = None, verbosity: int = 0, extra_vars: dict = None):
        playbook_name = playbook_name.replace("\\", "/")
        trigger = "manual" if not check_mode else "manual_check"
        
        # Create job record with params
        import json
        params_dict = {
            "limit": limit,
            "tags": tags,
            "verbosity": verbosity,
            "extra_vars": extra_vars
        }
        db_params = json.dumps(params_dict) if any(v is not None and v != "" and v != {} and v != 0 for v in params_dict.values()) else None
        
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger, params=db_params)
        
        self.db.add(job); self.db.commit(); self.db.refresh(job); job_id = job.id
            
        log_buffer = []
        lock = self._get_lock(playbook_name)
        if lock.locked():
            msg = f'<div class="log-error">Error: Playbook {playbook_name} is already running.</div>'
            yield msg
            job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
            self.db.add(job); self.db.commit()
            return
 
        async with lock:
            playbook_path = settings.PLAYBOOKS_DIR / playbook_name
            if not playbook_path.exists():
                msg = f'<div class="log-error">Error: Playbook {playbook_name} not found.</div>'
                yield msg
                job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                self.db.add(job); self.db.commit()
                return
 
            if "mock" in playbook_name.lower():
                 yield f'<div class="log-meta">Starting Mock Execution...</div>'
                 await asyncio.sleep(1)
                 yield f'<div class="log-success">Mock Process finished</div>'
                 return
 
            env_vars_db = self.db.exec(select(EnvVar)).all()
            custom_env = {ev.key: ev.value for ev in env_vars_db}
            custom_env.update({"ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOWS": "1"})
 
            cmd, error_msg = self._get_ansible_command(
                playbook_path, 
                check_mode=check_mode, 
                env_vars=custom_env,
                limit=limit,
                tags=tags,
                verbosity=verbosity,
                extra_vars=extra_vars
            )
            if not cmd:
                 yield error_msg
                 job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = error_msg; job.exit_code = 127
                 self.db.add(job); self.db.commit()
                 return
 
            try:
                env = os.environ.copy(); env.update(custom_env)
                print(f"DEBUG: Executing command: {cmd}")
                
                # Check for loop compatibility
                loop = asyncio.get_event_loop()
                if sys.platform == 'win32' and not isinstance(loop, asyncio.ProactorEventLoop):
                     print("WARNING: Not using ProactorEventLoop on Windows. Subprocesses might fail.")
 
                process = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.STDOUT, 
                    env=env,
                    cwd=str(playbook_path.parent) if not settings.USE_DOCKER else None
                )
                RunnerService._processes[playbook_name] = process
                
                if check_mode:
                    yield '<div class="log-changed" style="font-weight: bold; padding: 10px; border: 1px dashed #fbbf24; margin-bottom: 10px;">⚠️ DRY RUN MODE: No changes will be applied.</div>'
                
                msg = f'<div class="log-meta">Sible: Starting execution of {playbook_name}...</div>'
                yield msg; log_buffer.append(msg)
                
                while True:
                    line = await process.stdout.readline()
                    if not line: break
                    formatted_line = self.format_log_line(line.decode('utf-8', errors='replace').rstrip())
                    log_buffer.append(formatted_line); yield formatted_line
                
                await process.wait()
                exit_class = "log-success" if process.returncode == 0 else "log-error"
                yield f'<div class="{exit_class}">Sible: Process finished with exit code {process.returncode}</div>'
                
                job = self.db.get(JobRun, job_id)
                if job:
                    job.status = "success" if process.returncode == 0 else "failed"
                    job.end_time = datetime.utcnow()
                    job.log_output = "\n".join(log_buffer)
                    job.exit_code = process.returncode
                    self.db.add(job); self.db.commit()
                    self.notification_service.send_playbook_notification(playbook_name, job.status)
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_msg = str(e) or type(e).__name__
                yield f'<div class="log-error">Sible Error: Failed to start process: {err_msg}</div>'
                job = self.db.get(JobRun, job_id)
                if job:
                    job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = err_msg; job.exit_code = 1
                    self.db.add(job); self.db.commit()
            finally:
                if playbook_name in RunnerService._processes:
                    del RunnerService._processes[playbook_name]
 
    async def install_requirements(self, playbook_name: str):
        playbook_name = playbook_name.replace("\\", "/")
        playbook_path = settings.PLAYBOOKS_DIR / playbook_name
        # Simple validation
        if not str(playbook_path.resolve()).startswith(str(settings.PLAYBOOKS_DIR.resolve())):
             yield '<div class="log-error">Error: Invalid playbook path</div>'; return
 
        parent = playbook_path.parent
        req_file = "requirements.yml" if (parent / "requirements.yml").exists() else "requirements.yaml" if (parent / "requirements.yaml").exists() else None
        if not req_file:
            yield '<div class="log-error">Error: No requirements.yml found in directory.</div>'; return
 
        cmd, error_msg = self._get_ansible_command(
            playbook_path, 
            galaxy=True, 
            galaxy_req_file=req_file, 
            galaxy_cwd=parent
        )
        
        if not cmd:
            yield error_msg; return
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT, 
                cwd=str(parent), 
                env=os.environ.copy()
            )
            yield '<div class="log-meta">Sible: Starting installation of roles via ansible-galaxy...</div>'
            while True:
                line = await process.stdout.readline()
                if not line: break
                yield self.format_log_line(line.decode('utf-8', errors='replace').rstrip())
            await process.wait()
            yield f'<div class="log-success">Sible: Installation finished with code {process.returncode}</div>'
        except Exception as e:
            yield f'<div class="log-error">Sible Error: {str(e)}</div>'
 
    def cleanup_started_jobs(self):
        running_jobs = self.db.exec(select(JobRun).where(JobRun.status == "running")).all()
        count = len(running_jobs)
        if count > 0:
            print(f"[RunnerService] Found {count} zombie jobs. Cleaning up...")
            for job in running_jobs:
                job.status = "failed"
                if job.log_output: job.log_output += "\\n[SYSTEM] Job interrupted by server restart."
                else: job.log_output = "[SYSTEM] Job interrupted by server restart."
                self.db.add(job)
            self.db.commit()
            print(f"[RunnerService] Cleaned up {count} zombie jobs.")
