from pathlib import Path
from typing import Optional, Any, AsyncGenerator
import os
import shutil
import sys
import asyncio
import logging
import shlex
import html
from datetime import datetime
from sqlmodel import Session, select
from app.models import JobRun, EnvVar
from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.services.notification import NotificationService

settings = get_settings()
logger = logging.getLogger(__name__)

class RunnerService:
    """Orchestrates Ansible playbook executions across different environments.

    This service manages the execution lifecycle of Ansible playbooks, handling
    concurrency via locking, real-time log streaming through asynchronous generators,
    and platform-specific command construction (Docker, native host, or WSL).

    Attributes:
        db (Session): SQLModel database session for persistence.
        notification_service (NotificationService): Service for sending job alerts.
    """
    _locks: dict[str, asyncio.Lock] = {}
    _processes: dict[str, asyncio.subprocess.Process] = {}

    def __init__(self, db: Session):
        """Initializes the service with database and notification dependencies.

        Args:
            db: Current database session used for job tracking and settings retrieval.
        """
        self.db = db
        self.notification_service = NotificationService(db)

    @property
    def base_dir(self) -> Path:
        """Dynamically resolves the base directory for playbooks from database settings.

        Why: This allows users to change their playbook storage location in the
        settings UI without requiring a server restart. It falls back to a
        container-friendly default.

        Returns:
            Path object pointing to the playbook root directory.
        """
        from app.models import AppSettings
        from app.core.config import get_settings as get_app_settings
        db_settings = self.db.get(AppSettings, 1)
        if db_settings and db_settings.playbooks_path:
            return Path(db_settings.playbooks_path)
            
        return get_app_settings().PLAYBOOKS_DIR

    def _get_lock(self, playbook_name: str) -> asyncio.Lock:
        """Retrieves or creates a named lock for a specific playbook.

        Why: To prevent race conditions where multiple users or scheduled tasks
        attempt to run the same playbook concurrently, which could lead to
        inconsistent infrastructure states.

        Args:
            playbook_name: The unique name/path of the playbook to lock.

        Returns:
            An asyncio.Lock instance specific to that playbook.
        """
        if playbook_name not in RunnerService._locks:
            RunnerService._locks[playbook_name] = asyncio.Lock()
        return RunnerService._locks[playbook_name]

    @staticmethod
    def _get_ansible_command(
        playbook_path: Path, 
        playbooks_dir: Path,
        check_mode: bool = False, 
        env_vars: Optional[dict[str, str]] = None, 
        galaxy: bool = False, 
        galaxy_req_file: Optional[str] = None, 
        galaxy_cwd: Optional[Path] = None,
        limit: Optional[str] = None,
        tags: Optional[str] = None,
        verbosity: int = 0,
        extra_vars: Optional[dict[str, Any]] = None,
        inventory_path: Optional[Path] = None
    ) -> tuple[Optional[list[str]], Optional[str]]:
        """Constructs the command list for running Ansible or Ansible Galaxy.

        Why: Sible abstracts the execution environment. It prioritizes Docker for
        isolation, falls back to native execution, and provides a WSL path-mapping
        strategy for Windows hosts. This implementation uses direct list-based
        execution to prevent command injection.
        """
        base = playbooks_dir or settings.PLAYBOOKS_DIR
        inventory_file_name = "inventory.ini"
        
        if inventory_path:
             if inventory_path.is_absolute():
                 try:
                     rel_inv = inventory_path.resolve().relative_to(base.resolve())
                     inventory_file_name = rel_inv.as_posix()
                 except ValueError:
                     inventory_file_name = "inventory.ini"
             else:
                 inventory_file_name = str(inventory_path).replace("\\", "/")
        
        # 1. Try Docker execution if enabled
        if settings.USE_DOCKER:
            docker_bin = shutil.which("docker")
            if docker_bin:
                host_workdir = settings.HOST_WORKSPACE_PATH + "/playbooks" if settings.HOST_WORKSPACE_PATH else str(base.resolve())
                container_workdir = settings.DOCKER_WORKSPACE_PATH
                
                cmd = [
                    docker_bin, "run", "--rm",
                    "-v", f"{host_workdir}:{container_workdir}",
                    "-w", container_workdir
                ]
                
                if env_vars:
                    for k, v in env_vars.items():
                        cmd.extend(["-e", f"{k}={v}"])
                
                cmd.append(settings.DOCKER_IMAGE)
                
                if galaxy:
                    cmd.extend(["ansible-galaxy", "install", "-r", galaxy_req_file or "requirements.yml", "-p", "./roles"])
                else:
                    try:
                        rel_playbook = playbook_path.resolve().relative_to(base.resolve())
                        container_playbook_path = f"{container_workdir}/{rel_playbook.as_posix()}"
                    except ValueError:
                         container_playbook_path = f"{container_workdir}/{playbook_path.name}"
                    
                    cmd.extend(["ansible-playbook", container_playbook_path, "-i", f"{container_workdir}/{inventory_file_name}"])
                    if check_mode: cmd.append("--check")
                    if limit: cmd.extend(["--limit", limit])
                    if tags: cmd.extend(["--tags", tags])
                    if verbosity > 0: cmd.append(f"-{'v' * verbosity}")
                    if extra_vars:
                        import json
                        cmd.extend(["-e", json.dumps(extra_vars)])

                return cmd, None

        # 2. Try native host execution as fallback
        ansible_bin = shutil.which("ansible-playbook" if not galaxy else "ansible-galaxy")
        if ansible_bin:
            if galaxy:
                 cmd = [ansible_bin, "install", "-r", galaxy_req_file or "requirements.yml", "-p", "./roles"]
            else:
                 cmd = [ansible_bin, str(playbook_path), "-i", inventory_file_name]
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
 
                # WSL still requires some path translation, but we use list-based exec
                wsl_cmd = [wsl_bin]
                
                # Note: Setting env vars in WSL call
                if env_vars:
                    for k, v in env_vars.items():
                        if k.startswith(("ANSIBLE_", "SIB_")) or len(str(v)) < 100:
                            wsl_cmd.extend(["--env", f"{k}={v}"])

                if galaxy:
                     wsl_cwd = to_wsl_path(galaxy_cwd or base)
                     wsl_cmd.extend(["bash", "-c", f"cd {shlex.quote(wsl_cwd)} && ansible-galaxy install -r {shlex.quote(galaxy_req_file)} -p ./roles"])
                     # Note: galaxy still uses bash -c because of 'cd', but inputs are quoted.
                else:
                    wsl_playbook_path = to_wsl_path(playbook_path)
                    wsl_inventory_path = to_wsl_path(base / inventory_file_name)
                    
                    inner_wsl_cmd = ["ansible-playbook", wsl_playbook_path, "-i", wsl_inventory_path]
                    if check_mode: inner_wsl_cmd.append("--check")
                    if limit: inner_wsl_cmd.extend(["--limit", limit])
                    if tags: inner_wsl_cmd.extend(["--tags", tags])
                    if verbosity > 0: inner_wsl_cmd.append(f"-{'v' * verbosity}")
                    if extra_vars:
                        import json
                        inner_wsl_cmd.extend(["-e", json.dumps(extra_vars)])
                    
                    wsl_cmd.extend(inner_wsl_cmd)
                
                return wsl_cmd, None
                
            return None, '<div class="log-error">Error: Ansible not found (Docker/Host/WSL).</div>'
            
        return None, '<div class="log-error">Error: ansible-playbook executable not found in PATH.</div>'

    @staticmethod
    def format_log_line(line: str) -> str:
        """Applies HTML formatting and secret masking to a single Ansible log line.

        Why: Ansible's output is colored via ANSI codes in a terminal, which
        don't work in a browser. This method parses task headers and applies
        CSS classes. It also masks potential secrets to prevent exposure.
        """
        # Mask sensitive keywords
        sensitive_patterns = [
            r'ansible_become_pass\s*[=:]\s*(\S+)',
            r'ansible_password\s*[=:]\s*(\S+)',
            r'ansible_ssh_pass\s*[=:]\s*(\S+)',
            r'ansible_ssh_private_key\s*[=:]\s*(\S+)',
            r'ansible_ssh_private_key_file\s*[=:]\s*(\S+)',
            r'vault_password\s*[=:]\s*(\S+)',
            r'ansible_vault_password\s*[=:]\s*(\S+)',
            r'ANSIBLE_VAULT;[^\s]+',
            r'password\s*[=:]\s*(\S+)',
            r'secret\s*[=:]\s*(\S+)',
            r'token\s*[=:]\s*(\S+)',
            r'api_key\s*[=:]\s*(\S+)',
            r'auth\s*[=:]\s*(\S+)',
            r'key\s*[=:]\s*(\S+)'
        ]
        
        masked_line = line
        import re
        for pattern in sensitive_patterns:
            masked_line = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), "********"), masked_line, flags=re.IGNORECASE)

        css_class = ""
        if "TASK [" in masked_line or "PLAY [" in masked_line or "PLAY RECAP" in masked_line: css_class = "log-meta"
        elif "ok: [" in masked_line or "ok=" in masked_line: css_class = "log-success"
        elif "changed: [" in masked_line or "changed=" in masked_line: css_class = "log-changed"
        elif "fatal:" in masked_line or "failed=" in masked_line or "unreachable=" in masked_line: css_class = "log-error"
        elif "skipping:" in masked_line: css_class = "log-debug"
        escaped_line = html.escape(masked_line)
        return f'<div class="{css_class}">{escaped_line}</div>' if css_class else f'<div>{escaped_line}</div>'
 
    async def run_playbook_headless(
        self, 
        playbook_name: str, 
        check_mode: bool = False, 
        limit: str = None, 
        tags: str = None, 
        verbosity: int = 0, 
        extra_vars: dict = None, 
        username: str = None
    ) -> dict[str, Any]:
        """Executes a playbook in the background without real-time streaming to UI.

        Why: Used primarily by the scheduler or for quick automated checks where
        the user isn't actively watching the logs. It captures the full output and
        saves it to history in a single batch once complete.

        Args:
            playbook_name: Path to the playbook.
            check_mode: Whether to run in dry-run mode.
            limit: Specific hosts to target.
            tags: Specific tags to run.
            verbosity: Log level (0-4).
            extra_vars: Dynamic variables for the run.
            username: The agent or user who triggered this run.

        Returns:
            A dictionary containing 'success' (bool), 'output' (str), and 'rc' (int).
        """
        # Sync inventory before run
        from app.services.inventory import InventoryService
        InventoryService.sync_db_to_ini(self.db)

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
        
        job_target = limit if limit else "all"
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger, params=db_params, target=job_target, username=username)
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        job_id = job.id
 
        base = self.base_dir
        playbook_path = base / playbook_name
        if not playbook_path.exists():
            msg = f"Playbook {playbook_name} not found"
            job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
            self.db.add(job); self.db.commit()
            return {'success': False, 'output': msg, 'rc': 1}
 
        env_vars_db = self.db.exec(select(EnvVar)).all()
        custom_env = {ev.key: ev.value for ev in env_vars_db}
        custom_env.update({"ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOWS": "1", "ANSIBLE_HOST_KEY_CHECKING": "False"})
 
        # Create ephemeral inventory
        from app.services.inventory import InventoryService
        import shutil
        
        job_inv_dir = InventoryService.create_job_inventory(self.db, job_id)
        inv_path = job_inv_dir / "inventory.ini" if job_inv_dir else None
        
        if not inv_path:
             job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = "Failed to create inventory"; job.exit_code = 1
             self.db.add(job); self.db.commit()
             return {'success': False, 'output': "Failed to create inventory", 'rc': 1}
        cmd, error_msg = RunnerService._get_ansible_command(
            playbook_path, 
            playbooks_dir=base,
            check_mode=check_mode,
            env_vars=custom_env,
            limit=limit,
            tags=tags,
            verbosity=verbosity,
            extra_vars=extra_vars,
            inventory_path=inv_path
        )
        if not cmd:
            job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = error_msg; job.exit_code = 127
            self.db.add(job); self.db.commit()
            if job_inv_dir and job_inv_dir.exists(): shutil.rmtree(job_inv_dir)
            return {'success': False, 'output': error_msg, 'rc': 127}

        env = os.environ.copy()
        env.update(custom_env)
        env["PYTHONUNBUFFERED"] = "1"
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.STDOUT, 
                env=env,
                cwd=str(playbook_path.parent) if not settings.USE_DOCKER else None
            )
            stdout, _ = await process.communicate()
            output = stdout.decode('utf-8', errors='replace')
            
            job.status = "success" if process.returncode == 0 else "failed"
            job.end_time = datetime.utcnow()
            
            # If output is empty but process failed, provide a hint
            if not output.strip() and job.status == "failed":
                output = f"Error: Process failed with exit code {process.returncode} but produced no output. This might indicate an issue with finding the executable or permissions."
                
            job.log_output = "\n".join([self.format_log_line(line) for line in output.splitlines()])
            job.exit_code = process.returncode
            self.db.add(job); self.db.commit()
            
            # Apply retention policies
            from app.services.history import HistoryService
            HistoryService(self.db).apply_retention_policies(playbook_name)
            
            self.notification_service.send_playbook_notification(playbook_name, job)
            return {'success': process.returncode == 0, 'output': output, 'rc': process.returncode}
        except Exception as e:
            msg = str(e)
            job = self.db.get(JobRun, job_id)
            if job:
                job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
                self.db.add(job); self.db.commit()
            return {'success': False, 'output': msg, 'rc': 1}
        finally:
            if job_inv_dir and job_inv_dir.exists():
                try: shutil.rmtree(job_inv_dir)
                except Exception: pass
 
    def stop_playbook(self, playbook_name: str) -> bool:
        """Terminates a running playbook process by its name.

        Why: Gives users control to abort runaway or accidentally triggered
        playbooks immediately.

        Args:
            playbook_name: The name of the playbook whose process should be stopped.

        Returns:
            True if the process was successfully signaled to terminate, False if
            no such process was found.
        """
        playbook_name = playbook_name.replace("\\", "/")
        process = RunnerService._processes.get(playbook_name)
        if process:
            try:
                process.terminate()
                return True
            except (ProcessLookupError, AttributeError):
                return False
        return False
 
    async def run_playbook(
        self, 
        playbook_name: str, 
        check_mode: bool = False, 
        limit: Optional[str] = None, 
        tags: Optional[str] = None, 
        verbosity: int = 0, 
        extra_vars: Optional[dict[str, Any]] = None, 
        username: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Executes an Ansible playbook and yields formatted log lines in real-time.

        Args:
            playbook_name: The name of the playbook file relative to the playbooks directory.
            check_mode: If True, runs the playbook in dry-run mode (--check).
            limit: Optional Ansible limit string.
            tags: Optional Ansible tags string.
            verbosity: Integer 0-4 for Ansible verbosity levels.
            extra_vars: Dictionary of extra variables for Ansible.
            username: The username of the person triggering the run.

        Yields:
            HTML-formatted log lines.
        """
        playbook_name = playbook_name.replace("\\", "/")
        trigger = "manual" if not check_mode else "manual_check"
        
        # Create job record with params
        params_dict = {
            "limit": limit,
            "tags": tags,
            "verbosity": verbosity,
            "extra_vars": extra_vars
        }
        import json
        db_params = json.dumps(params_dict) if any(v is not None and v != "" and v != {} and v != 0 for v in params_dict.values()) else None
        
        job_target = limit if limit else "all"
        job = JobRun(playbook=playbook_name, status="running", trigger=trigger, params=db_params, target=job_target, username=username)
        
        self.db.add(job); self.db.commit(); self.db.refresh(job); job_id = job.id

        # Prepare isolated job directory
        from app.services.inventory import InventoryService
        job_inv_dir = InventoryService.create_job_inventory(self.db, job_id)
        if not job_inv_dir:
             msg = '<div class="log-error">Error: Failed to create isolated job inventory.</div>'
             yield msg
             job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
             self.db.add(job); self.db.commit()
             return
            
        log_buffer = []
        lock = self._get_lock(playbook_name)
        if lock.locked():
            msg = f'<div class="log-error">Error: Playbook {playbook_name} is already running.</div>'
            yield msg
            job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = msg; job.exit_code = 1
            self.db.add(job); self.db.commit()
            return
 
        async with lock:
            base = self.base_dir
            playbook_path = base / playbook_name
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
                 
                 # Update job status for mock playbook
                 job = self.db.get(JobRun, job_id)
                 if job:
                     job.status = "success"
                     job.end_time = datetime.utcnow()
                     job.log_output = "Mock execution completed"
                     job.exit_code = 0
                     self.db.add(job)
                     self.db.commit()
                 return
 
            env_vars_db = self.db.exec(select(EnvVar)).all()
            custom_env = {ev.key: (decrypt_secret(ev.value) if ev.is_secret else ev.value) for ev in env_vars_db}
            custom_env.update({"ANSIBLE_FORCE_COLOR": "0", "ANSIBLE_NOCOWS": "1", "ANSIBLE_HOST_KEY_CHECKING": "False"})
 
            # Create ephemeral inventory
            from app.services.inventory import InventoryService
            job_inv_dir = InventoryService.create_job_inventory(self.db, job_id)
            inv_path = job_inv_dir / "inventory.ini" if job_inv_dir else None
 
            cmd, error_msg = RunnerService._get_ansible_command(
                playbook_path, 
                playbooks_dir=base,
                check_mode=check_mode, 
                env_vars=custom_env,
                limit=limit,
                tags=tags,
                verbosity=verbosity,
                extra_vars=extra_vars,
                inventory_path=inv_path
            )
            if not cmd:
                 yield error_msg if error_msg else "Unknown command generation error"
                 job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = error_msg; job.exit_code = 127
                 self.db.add(job); self.db.commit()
                 if job_inv_dir and job_inv_dir.exists(): shutil.rmtree(job_inv_dir)
                 return
 
            try:
                env = os.environ.copy(); env.update(custom_env)
                logger.info(f"[Job {job_id}] Executing playbook {playbook_name}")
                
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd, 
                        stdout=asyncio.subprocess.PIPE, 
                        stderr=asyncio.subprocess.STDOUT, 
                        env=env,
                        cwd=str(playbook_path.parent) if not settings.USE_DOCKER else None
                    )
                    logger.info(f"Process created for {playbook_name}, PID: {process.pid}")
                except Exception as proc_error:
                    logger.error(f"Failed to create subprocess: {proc_error}")
                    raise
                    
                RunnerService._processes[playbook_name] = process
                
                # Store PID for monitoring
                RunnerService._process_monitors = getattr(RunnerService, '_process_monitors', {})
                RunnerService._process_monitors[job_id] = {
                    'process': process,
                    'playbook_name': playbook_name,
                    'log_buffer': log_buffer,
                    'start_time': datetime.utcnow()
                }
                logger.info(f"Added job {job_id} ({playbook_name}) to process monitors")
                
                if check_mode:
                    yield '<div class="log-changed" style="font-weight: bold; padding: 10px; border: 1px dashed #fbbf24; margin-bottom: 10px;">⚠️ DRY RUN MODE: No changes will be applied.</div>'
                
                msg = f'<div class="log-meta">Sible: Starting execution of {playbook_name}...</div>'
                yield msg; log_buffer.append(msg)
                
                # Stream output to client
                try:
                    while True:
                        line = await process.stdout.readline()
                        if not line: break
                        formatted_line = self.format_log_line(line.decode('utf-8', errors='replace').rstrip())
                        log_buffer.append(formatted_line)
                        yield formatted_line
                    
                    # If we made it here, the client is still connected
                    await process.wait()
                    exit_class = "log-success" if process.returncode == 0 else "log-error"
                    yield f'<div class="{exit_class}">Sible: Process finished with exit code {process.returncode}</div>'
                    
                    # Update job status (monitor will skip if already updated)
                    job = self.db.get(JobRun, job_id)
                    if job and job.status == "running":
                        job.status = "success" if process.returncode == 0 else "failed"
                        job.end_time = datetime.utcnow()
                        job.log_output = "\n".join(log_buffer)
                        job.exit_code = process.returncode
                        self.db.add(job)
                        self.db.commit()
                        
                        # Apply retention policies
                        from app.services.history import HistoryService
                        HistoryService(self.db).apply_retention_policies(playbook_name)
                        
                        self.notification_service.send_playbook_notification(playbook_name, job)
                        
                        # Remove from monitors since we updated it
                        if job_id in RunnerService._process_monitors:
                            del RunnerService._process_monitors[job_id]
                            logger.info(f"Removed job {job_id} from monitors (client stayed connected)")
                except (GeneratorExit, asyncio.CancelledError):
                    # Client disconnected - start background task to continue reading stdout
                    logger.info(f"Client disconnected from {playbook_name}, starting background reader (job_id={job_id})")
                    
                    async def continue_reading_stdout():
                        """Continue reading stdout to prevent process from blocking."""
                        try:
                            while True:
                                line = await process.stdout.readline()
                                if not line:
                                    break
                                formatted_line = self.format_log_line(line.decode('utf-8', errors='replace').rstrip())
                                log_buffer.append(formatted_line)
                            await process.wait()
                            logger.info(f"Background reader completed for job {job_id}, exit code: {process.returncode}")
                        except Exception as e:
                            logger.exception(f"Error in background reader for job {job_id}: {e}")
                    
                    # Start the background reader task
                    asyncio.create_task(continue_reading_stdout())
                    raise
                
            except Exception as e:
                logger.exception(f"Error during playbook execution of {playbook_name}")
                err_msg = str(e) or type(e).__name__
                yield f'<div class="log-error">Sible Error: Failed to start process: {err_msg}</div>'
                job = self.db.get(JobRun, job_id)
                if job:
                    job.status = "failed"; job.end_time = datetime.utcnow(); job.log_output = err_msg; job.exit_code = 1
                    self.db.add(job); self.db.commit()
            finally:
                if playbook_name in RunnerService._processes:
                    del RunnerService._processes[playbook_name]
                if job_inv_dir and job_inv_dir.exists():
                    try: shutil.rmtree(job_inv_dir)
                    except Exception: pass
 
    async def install_requirements(self, playbook_name: str) -> AsyncGenerator[str, None]:
        """Installs Ansible galaxy requirements for a playbook directory.

        Why: Ensures that all necessary third-party roles and collections are
        available locally before a playbook execution starts, preventing
        'role not found' errors.

        Args:
            playbook_name: The playbook whose requirements should be installed.

        Yields:
            Progress log lines from ansible-galaxy.
        """
        playbook_name = playbook_name.replace("\\", "/")
        base = self.base_dir
        playbook_path = base / playbook_name
        # Simple validation
        if not str(playbook_path.resolve()).startswith(str(base.resolve())):
             yield '<div class="log-error">Error: Invalid playbook path</div>'; return
 
        parent = playbook_path.parent
        req_file = "requirements.yml" if (parent / "requirements.yml").exists() else "requirements.yaml" if (parent / "requirements.yaml").exists() else None
        if not req_file:
            yield '<div class="log-error">Error: No requirements.yml found in directory.</div>'; return
 
        cmd, error_msg = RunnerService._get_ansible_command(
            playbook_path, 
            playbooks_dir=base,
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
 
    def cleanup_started_jobs(self) -> None:
        """Force-fails any jobs that were left in a 'running' state.

        Why: If the server crashes or restarts, jobs marked as 'running' will
        be stuck forever. This cleanup routine runs at server startup to ensure
        history reflects that those jobs were interrupted.
        """
        running_jobs = self.db.exec(select(JobRun).where(JobRun.status == "running")).all()
        count = len(running_jobs)
        if count > 0:
            logger.info(f"Found {count} zombie jobs. Cleaning up...")
            for job in running_jobs:
                job.status = "failed"
                if job.log_output: job.log_output += "\\n[SYSTEM] Job interrupted by server restart."
                else: job.log_output = "[SYSTEM] Job interrupted by server restart."
                self.db.add(job)
            self.db.commit()
            logger.info(f"Cleaned up {count} zombie jobs.")
