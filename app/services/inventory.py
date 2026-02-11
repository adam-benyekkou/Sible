from typing import Optional, Any
from sqlmodel import Session, select, func, or_
from pathlib import Path
from app.models import Host, EnvVar
import shutil
import asyncio
import sys
import os
import shlex
import logging
import uuid
from app.utils.network import check_ssh
from app.core.config import get_settings
from app.core.security import decrypt_secret

settings = get_settings()
logger = logging.getLogger(__name__)

class InventoryService:
    """Manages Ansible inventory records, SSH connectivity, and dynamic INI generation.

    This service acts as the bridge between the SQLModel database (user-friendly UI)
    and the raw Ansible `inventory.ini` format. It handles host registration,
    automatic status health checks, and ephemeral inventory creation for job isolation.

    Attributes:
        INVENTORY_FILE (Path): Path to the persistent global inventory file.
    """
    INVENTORY_FILE: Path = settings.PLAYBOOKS_DIR / "inventory.ini"
    
    @staticmethod
    def sanitize_ansible_name(name: str) -> str:
        """Sanitizes strings for Ansible compatibility by removing illegal characters.

        Why: Ansible is sensitive to host and group names containing spaces or
        certain special characters. This ensures that user input in the UI
        doesn't break the generated CLI commands.

        Args:
            name: The raw string (e.g., from a form input).

        Returns:
            A sanitized string with spaces replaced by underscores.
        """
        if not name: return ""
        return name.strip().replace(" ", "_")

    
    @staticmethod
    def get_inventory_content() -> str:
        """Reads the raw content of the global inventory.ini file.

        Why: Provides the 'Source of Truth' for the raw text editor in the UI.

        Returns:
            The complete contents of the inventory file as a string.
        """
        if not InventoryService.INVENTORY_FILE.exists():
            InventoryService.INVENTORY_FILE.write_text("[all]\nlocalhost ansible_connection=local\n", encoding="utf-8")
        return InventoryService.INVENTORY_FILE.read_text(encoding="utf-8")

    @staticmethod
    def save_inventory_content(content: str) -> bool:
        """Overwrites the global inventory.ini file with new content.

        Args:
            content: The new raw INI text.

        Returns:
            True if write was successful, False otherwise.
        """
        try:
            InventoryService.INVENTORY_FILE.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    @staticmethod
    def sync_db_to_ini(db: Session) -> bool:
        """Exports all database host records to the physical inventory.ini file.

        Why: Sible uses the database as the primary UI storage, but Ansible CLI
        requires a filesystem-based inventory. This sync ensures Ansible always
        uses the latest host data, including dynamically decrypted SSH keys.

        Args:
            db: Current database session.

        Returns:
            True if sync succeeded, False if an error occurred.
        """
        try:
            hosts = db.exec(select(Host)).all()
            lines = []
            
            groups: dict[str, list[Host]] = {}
            for host in hosts:
                g = host.group_name or "all"
                if g not in groups:
                    groups[g] = []
                groups[g].append(host)
            
            for group, group_hosts in groups.items():
                sanitized_group = InventoryService.sanitize_ansible_name(group or "all")
                lines.append(f"[{sanitized_group}]")
                for h in group_hosts:
                    sanitized_alias = InventoryService.sanitize_ansible_name(h.alias)
                    line = f"{sanitized_alias} ansible_host={h.hostname} ansible_user={h.ssh_user} ansible_port={h.ssh_port}"
                    
                    if h.ssh_key_path:
                        line += f" ansible_ssh_private_key_file={h.ssh_key_path}"
                    elif h.ssh_key_secret:
                        env_var = next((e for e in db.exec(select(EnvVar).where(EnvVar.key == h.ssh_key_secret)).all()), None)
                        if env_var and env_var.value:
                            secret_val = decrypt_secret(env_var.value) if env_var.is_secret else env_var.value
                            
                            # Use job-specific key isolation if job_id is provided
                            if job_id:
                                keys_dir = settings.BASE_DIR / ".jobs" / job_id / "keys"
                            else:
                                keys_dir = settings.PLAYBOOKS_DIR / "keys"
                                
                            keys_dir.mkdir(parents=True, exist_ok=True)
                            key_file = keys_dir / f"{h.alias}.pem"
                            
                            if "\\n" in secret_val: secret_val = secret_val.replace("\\n", "\n")
                            if not secret_val.endswith("\n"): secret_val += "\n"
                            
                            try:
                                key_file.write_text(secret_val, encoding="utf-8")
                                os.chmod(key_file, 0o600)
                            except Exception as e:
                                logger.error(f"Failed to write key file for {h.alias}: {e}")
                            
                            if settings.USE_DOCKER:
                                 # Docker mapping remains consistent if we mount .jobs
                                 worker_keys_path = f"{settings.DOCKER_WORKSPACE_PATH}/.jobs/{job_id}/keys" if job_id else f"{settings.DOCKER_WORKSPACE_PATH}/keys"
                                 line += f" ansible_ssh_private_key_file={worker_keys_path}/{h.alias}.pem"
                            else:
                                 line += f" ansible_ssh_private_key_file={key_file.resolve()}"
                        else:
                            line += f" # Sible:SecretNotFound={h.ssh_key_secret}"
                    
                    lines.append(line)
                lines.append("")

            content = "\n".join(lines)
            InventoryService.save_inventory_content(content)
            return True
        except Exception as e:
            logger.error(f"Failed to sync inventory: {e}")
            return False

    @staticmethod
    async def ping_all() -> str:
        """Runs the Ansible 'ping' module across all hosts in the inventory.

        Why: Provides a connectivity baseline. It verifies that Ansible can
        not only reach the IP but also successfully authenticate via SSH.

        Returns:
            A string containing the raw stdout/stderr from the ansible-ping command.
        """
        ansible_bin = shutil.which("ansible")
        if not ansible_bin and sys.platform == "win32":
             wsl_bin = shutil.which("wsl")
             if wsl_bin:
                abs_p = InventoryService.INVENTORY_FILE.resolve()
                drive = abs_p.drive.strip(':').lower()
                parts = list(abs_p.parts[1:])
                wsl_path = f"/mnt/{drive}/" + "/".join(parts)
                # Sanitize using shlex.quote for the shell command inside WSL
                cmd = [wsl_bin, "bash", "-c", f"ansible all -m ping -i {shlex.quote(wsl_path)}"]
             else: return "Ansible not found. If using Windows, please run Sible inside WSL or install Ansible locally."
        elif not ansible_bin: return "Ansible not found. Please install it to use ping."
        else: cmd = ["ansible", "all", "-m", "ping", "-i", str(InventoryService.INVENTORY_FILE)]
        try:
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=os.environ.copy())
            stdout, _ = await process.communicate()
            return stdout.decode() if stdout else "No output from ansible."
        except Exception as e: return f"Error running ping: {str(e)}"

    @staticmethod
    async def verify_connection(hostname: str, user: str, port: int, key_path: str = None) -> bool:
        """Performs a lightweight TCP handshake to check if SSH port is open.

        Why: Faster than running a full Ansible ping for quick UI feedback
        during host creation or editing.

        Args:
            hostname: Target IP or FQDN.
            user: SSH username (currently unused in TCP check).
            port: SSH port (default 22).
            key_path: Path to SSH key (currently unused in TCP check).

        Returns:
            True if the port responded, False otherwise.
        """
        is_online, _ = await check_ssh(hostname, port, timeout=3.0)
        return is_online

    @staticmethod
    def get_hosts_paginated(
        db: Session, 
        page: int = 1, 
        limit: int = 20, 
        search: str = None
    ) -> tuple[list[Host], int]:
        """Retrieves a subset of hosts with filtering and pagination.

        Args:
            db: Database session.
            page: Current page number (1-indexed).
            limit: Number of results per page.
            search: Optional string to filter by alias, hostname, or group.

        Returns:
            A tuple of (list_of_hosts, total_count_before_pagination).
        """
        offset = (page - 1) * limit
        statement = select(Host).order_by(Host.alias)
        
        # Total count
        count_statement = select(func.count()).select_from(Host)
        
        if search:
            search_filter = or_(
                Host.alias.ilike(f"%{search}%"),
                Host.hostname.ilike(f"%{search}%"),
                Host.group_name.ilike(f"%{search}%")
            )
            statement = statement.where(search_filter)
            count_statement = count_statement.where(search_filter)
        
        total_count = db.exec(count_statement).one()
        hosts = db.exec(statement.offset(offset).limit(limit)).all()
        return hosts, total_count


    @staticmethod
    def import_ini_to_db(db: Session, content: str = None) -> bool:
        """Parses an Ansible-formatted INI string and populates the database.

        Why: Allows power users to bulk-import infrastructure by pasting a
        standard Ansible inventory. It performs a destructive sync where the
        INI content becomes the new Source of Truth for the DB.

        Args:
            db: Database session.
            content: Raw INI string. If None, reads from the global INI file.

        Returns:
            True if import was successful, False otherwise.
        """
        try:
            if content is None:
                content = InventoryService.get_inventory_content()
            
            # Simple INI Parser tailored for Ansible format
            current_group = "all"
            
            # Remove all existing hosts? YES, to ensure sync.
            db.exec(Host.__table__.delete())
            
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith(';') or (line.startswith('#') and 'Sible:' not in line):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_group = InventoryService.sanitize_ansible_name(line[1:-1])
                    continue
                
                parts = line.split()
                if not parts: continue
                
                alias = InventoryService.sanitize_ansible_name(parts[0])
                hostname = alias # Default
                ssh_user = "root"
                ssh_port = 22
                ssh_key_path = None
                ssh_key_secret = None
                
                for part in parts[1:]:
                    if '=' in part:
                        k, v = part.split('=', 1)
                        if k == 'ansible_host': hostname = v
                        elif k == 'ansible_user': ssh_user = v
                        elif k == 'ansible_port': ssh_port = int(v) if v.isdigit() else 22
                        elif k == 'ansible_ssh_private_key_file': ssh_key_path = v
                
                # Check for Sible comments
                if '#' in line:
                    comment = line.split('#', 1)[1]
                    if 'Sible:' in comment:
                        if 'ssh_key_secret=' in comment:
                            try: ssh_key_secret = comment.split('ssh_key_secret=')[1].split()[0]
                            except: pass

                host = Host(
                    alias=alias,
                    hostname=hostname,
                    ssh_user=ssh_user,
                    ssh_port=ssh_port,
                    ssh_key_path=ssh_key_path,
                    ssh_key_secret=ssh_key_secret,
                    group_name=current_group
                )
                db.add(host)
            
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to import INI: {e}")
            db.rollback()
            return False

    @staticmethod
    async def refresh_all_statuses(db: Session) -> None:
        """Updates health status (online/offline) and latency for all hosts in parallel.

        Why: Keeps the dashboard 'Status' accurately reflecting the current
        state of the infrastructure. Uses asyncio for high concurrency when
        dealing with many nodes.

        Args:
            db: Database session.
        """
        hosts = db.exec(select(Host)).all()
        
        async def check_host(h):
            is_online, latency = await check_ssh(h.hostname, h.ssh_port)
            return h.id, is_online, latency

        tasks = [check_host(h) for h in hosts]
        results = await asyncio.gather(*tasks)
        
        # Apply results and commit once
        for host_id, is_online, latency in results:
            h = next((x for x in hosts if x.id == host_id), None)
            if h:
                h.status = "online" if is_online else "offline"
                h.latency = latency
                db.add(h)
        
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Failed to commit inventory status refresh: {e}")
            db.rollback()

    @staticmethod
    def create_job_inventory(db: Session, job_id: int) -> Optional[Path]:
        """Generates an isolated, ephemeral inventory directory for a specific job run.

        Why: Running heavy playbooks against a shared global inventory file
        could lead to conflicts if two jobs run at once. This method creates
        a unique directory with its own inventory and extracted SSH keys, ensuring
        perfect job isolation.

        Args:
            db: Database session.
            job_id: Unique ID of the job run.

        Returns:
            Path to the job's temporary directory, or None if creation failed.
        """
        try:
            job_dir = settings.PLAYBOOKS_DIR / ".jobs" / str(job_id)
            if job_dir.exists():
                shutil.rmtree(job_dir)
            job_dir.mkdir(parents=True, exist_ok=True)
            keys_dir = job_dir / "keys"
            keys_dir.mkdir(exist_ok=True)
            
            hosts = db.exec(select(Host)).all()
            lines = []
            
            # Group by group_name
            groups = {}
            for host in hosts:
                g = host.group_name or "all"
                if g not in groups:
                    groups[g] = []
                groups[g].append(host)
            
            for group, group_hosts in groups.items():
                sanitized_group = InventoryService.sanitize_ansible_name(group or "all")
                lines.append(f"[{sanitized_group}]")
                for h in group_hosts:
                    sanitized_alias = InventoryService.sanitize_ansible_name(h.alias)
                    line = f"{sanitized_alias} ansible_host={h.hostname} ansible_user={h.ssh_user} ansible_port={h.ssh_port}"
                    
                    if h.ssh_key_path:
                        line += f" ansible_ssh_private_key_file={h.ssh_key_path}"
                    elif h.ssh_key_secret:
                        # Resolve secret to file in job_dir/keys
                        env_var = next((e for e in db.exec(select(EnvVar).where(EnvVar.key == h.ssh_key_secret)).all()), None)
                        if env_var and env_var.value:
                            secret_val = decrypt_secret(env_var.value) if env_var.is_secret else env_var.value
                            key_file = keys_dir / f"{h.alias}.pem"
                            
                            # Ensure valid format
                            if "\\n" in secret_val: secret_val = secret_val.replace("\\n", "\n")
                            if not secret_val.endswith("\n"): secret_val += "\n"
                            
                            try:
                                key_file.write_text(secret_val, encoding="utf-8")
                                try: os.chmod(key_file, 0o600)
                                except: pass
                            except Exception as e:
                                logger.error(f"Failed to write key file for {h.alias}: {e}")
                            
                            # Path relative to inventory file
                            line += f" ansible_ssh_private_key_file=keys/{h.alias}.pem"
                        else:
                            line += f" # Sible:SecretNotFound={h.ssh_key_secret}"
                    
                    lines.append(line)
                lines.append("")

            content = "\n".join(lines)
            inv_file = job_dir / "inventory.ini"
            inv_file.write_text(content, encoding="utf-8")
            
            return job_dir
            
        except Exception as e:
            logger.error(f"Failed to create job inventory: {e}")
            return None

