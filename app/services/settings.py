from sqlmodel import Session
from app.config import get_settings
from app.models import AppSettings
from pathlib import Path
import shutil
import sys
import os
import asyncio

settings_conf = get_settings()

class SettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get_settings(self) -> AppSettings:
        settings = self.db.get(AppSettings, 1)
        if not settings:
            settings = AppSettings(id=1)
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        return settings

    def update_settings(self, data: dict) -> AppSettings:
        settings = self.get_settings()
        for k, v in data.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def get_env_vars(self):
        from app.models import EnvVar
        from sqlmodel import select
        return self.db.exec(select(EnvVar)).all()

    def create_env_var(self, key: str, value: str, is_secret: bool):
        from app.models import EnvVar
        env_var = EnvVar(key=key, value=value, is_secret=is_secret)
        self.db.add(env_var)
        self.db.commit()
        return env_var

    def delete_env_var(self, env_id: int):
        from app.models import EnvVar
        env_var = self.db.get(EnvVar, env_id)
        if env_var:
            key = env_var.key
            self.db.delete(env_var)
            self.db.commit()
            return key
        return None

    def get_env_var(self, env_id: int):
        from app.models import EnvVar
        return self.db.get(EnvVar, env_id)

    def update_env_var(self, env_id: int, key: str, value: str, is_secret: bool):
        from app.models import EnvVar
        env_var = self.db.get(EnvVar, env_id)
        if env_var:
            env_var.key = key
            if is_secret:
                env_var.is_secret = True
                if value.strip():
                    env_var.value = value
            else:
                env_var.is_secret = False
                env_var.value = value
                
            self.db.add(env_var)
            self.db.commit()
            self.db.refresh(env_var)
            return env_var
        return None

class InventoryService:
    INVENTORY_FILE = Path("inventory.ini")
    
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
            return stdout.decode('utf-8', errors='replace')
        except Exception as e: return f"Error running ping: {str(e)}"
