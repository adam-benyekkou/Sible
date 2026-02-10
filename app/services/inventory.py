from typing import List, Dict, Optional
from sqlmodel import Session, select
from pathlib import Path
from app.models import Host, EnvVar
import shutil
import asyncio
import sys
import os
import logging
import uuid
from app.utils.network import check_ssh

from app.core.config import get_settings
settings = get_settings()

class InventoryService:
    INVENTORY_FILE = settings.PLAYBOOKS_DIR / "inventory.ini"
    
    @staticmethod
    def sanitize_ansible_name(name: str) -> str:
        """
        Sanitizes names (groups or aliases) for Ansible compatibility (no spaces).
        """
        if not name: return ""
        # Ansible names: [a-zA-Z0-9_-]
        # We replace spaces with underscores and strip
        return name.strip().replace(" ", "_")

    
    @staticmethod
    def get_inventory_content() -> str:
        if not InventoryService.INVENTORY_FILE.exists():
            InventoryService.INVENTORY_FILE.write_text("[all]\nlocalhost ansible_connection=local\n", encoding="utf-8")
        return InventoryService.INVENTORY_FILE.read_text(encoding="utf-8")

    @staticmethod
    def save_inventory_content(content: str) -> bool:
        try:
            InventoryService.INVENTORY_FILE.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    @staticmethod
    def sync_db_to_ini(db: Session) -> bool:
        """
        Reads all Host records from DB and generates inventory.ini.
        Overwrites the existing file.
        """
        try:
            hosts = db.exec(select(Host)).all()
            lines = []
            
            # Group by group_name
            groups = {}
            for host in hosts:
                g = host.group_name or "all"
                if g not in groups:
                    groups[g] = []
                groups[g].append(host)
            
            # Write 'all' group first (or loose hosts) if any, though Ansible structure usually varies
            # For simplicity, we'll write [group_name] blocks
            
            for group, group_hosts in groups.items():
                sanitized_group = InventoryService.sanitize_ansible_name(group or "all")
                lines.append(f"[{sanitized_group}]")
                for h in group_hosts:
                    sanitized_alias = InventoryService.sanitize_ansible_name(h.alias)
                    line = f"{sanitized_alias} ansible_host={h.hostname} ansible_user={h.ssh_user} ansible_port={h.ssh_port}"
                    
                    if h.ssh_key_path:
                        line += f" ansible_ssh_private_key_file={h.ssh_key_path}"
                    elif h.ssh_key_secret:
                        # Resolve secret to file
                        env_var = next((e for e in db.exec(select(EnvVar).where(EnvVar.key == h.ssh_key_secret)).all()), None)
                        if env_var and env_var.value:
                            secret_val = env_var.value
                            keys_dir = settings.PLAYBOOKS_DIR / "keys"
                            keys_dir.mkdir(exist_ok=True)
                            key_file = keys_dir / f"{h.alias}.pem"
                            
                            # Ensure valid format
                            if "\\n" in secret_val: secret_val = secret_val.replace("\\n", "\n")
                            if not secret_val.endswith("\n"): secret_val += "\n"
                            
                            try:
                                key_file.write_text(secret_val, encoding="utf-8")
                                os.chmod(key_file, 0o600)
                            except Exception as e:
                                logger.error(f"Failed to write key file for {h.alias}: {e}")
                            
                            # Path for Ansible
                            if settings.USE_DOCKER:
                                 # DOCKER_WORKSPACE_PATH is /ansible
                                 # key file is keys/foo.pem relative to playbook dir
                                 line += f" ansible_ssh_private_key_file={settings.DOCKER_WORKSPACE_PATH}/keys/{h.alias}.pem"
                            else:
                                 line += f" ansible_ssh_private_key_file={key_file.resolve()}"
                        else:
                            line += f" # Sible:SecretNotFound={h.ssh_key_secret}"
                    
                    lines.append(line)
                lines.append("") # Empty line between groups

            content = "\n".join(lines)
            InventoryService.save_inventory_content(content)
            return True
        except Exception as e:
            logger.error(f"Failed to sync inventory: {e}")
            return False

    @staticmethod
    async def ping_all() -> str:
        if not InventoryService.INVENTORY_FILE.exists(): return "No inventory file found."
        ansible_bin = shutil.which("ansible")
        if not ansible_bin and sys.platform == "win32":
             wsl_bin = shutil.which("wsl")
             if wsl_bin:
                abs_p = InventoryService.INVENTORY_FILE.resolve()
                drive = abs_p.drive.strip(':').lower()
                parts = list(abs_p.parts[1:])
                wsl_path = f"/mnt/{drive}/" + "/".join(parts)
                cmd = [wsl_bin, "bash", "-c", f"ansible all -m ping -i '{wsl_path}'"]
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
        """
        Verifies connection to a specific host using a simple TCP port check.
        """
        is_online, _ = await check_ssh(hostname, port, timeout=3.0)
        return is_online

    @staticmethod
    def get_hosts_paginated(db: Session, page: int = 1, limit: int = 20, search: str = None) -> tuple[List[Host], int]:
        offset = (page - 1) * limit
        statement = select(Host).order_by(Host.alias)
        
        # Total count
        from sqlmodel import func, or_
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
        """
        Parses inventory.ini content and repopulates the Host table.
        This allows the text editor to be the source of truth.
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
    async def refresh_all_statuses(db: Session):
        """
        Iterates through all hosts and updates their status/latency.
        Batch commit at the end for efficiency.
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
    def create_job_inventory(db: Session, job_id: str) -> Path:
        """
        Creates a temporary inventory and key files for a specific job.
        Returns the path to the inventory directory.
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
                            secret_val = env_var.value
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

