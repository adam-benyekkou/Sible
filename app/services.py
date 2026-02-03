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
    def list_playbooks() -> List[str]:
        """
        Scans the playbooks directory and returns a list of .yaml/.yml files.
        """
        if not PLAYBOOKS_DIR.exists():
            PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            return []
            
        extensions = {".yaml", ".yml"}
        playbooks = [
            f.name for f in PLAYBOOKS_DIR.iterdir() 
            if f.is_file() and f.suffix.lower() in extensions
        ]
        return sorted(playbooks)

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

class RunnerService:
    @staticmethod
    async def run_playbook(playbook_name: str):
        """
        Runs an ansible-playbook and yields the output line by line.
        """
        playbook_path = PLAYBOOKS_DIR / playbook_name
        if not playbook_path.exists():
            yield f'<div class="log-error">❌ Error: Playbook {playbook_name} not found.</div>'
            return


        
        # Check if ansible-playbook is installed
        ansible_bin = shutil.which("ansible-playbook")
        cmd = []
        
        if ansible_bin:
            cmd = [ansible_bin, str(playbook_path)]
        elif sys.platform == "win32":
            # Try via WSL
            wsl_bin = shutil.which("wsl")
            if wsl_bin:
                # Convert path to WSL format (naive)
                # sible/playbooks/hello.yaml -> /mnt/c/Users/...
                # This is tricky without wslpath. Let's just try running it assuming relative path if within WSL mount?
                # Actually, simplest is to warn user.
                yield f'<div class="log-changed">⚠️ Ansible not found on Windows Host.</div>'
                yield f'<div class="log-meta">ℹ️ Tip: Run this app via Docker to execute playbooks.</div>'
                # Optional: Mock mode for UI testing
                if "mock" in playbook_name.lower() or "hello" in playbook_name.lower():
                     yield f'<div class="log-meta">🧪 Starting Mock Execution for UI Testing...</div>'
                     await asyncio.sleep(1)
                     yield f'<div class="log-meta">TASK [Gathering Facts] ***************************************************************</div>'
                     await asyncio.sleep(0.5)
                     yield f'<div class="log-success">ok: [localhost]</div>'
                     await asyncio.sleep(0.5)
                     yield f'<div class="log-meta">TASK [debug] *************************************************************************</div>'
                     await asyncio.sleep(0.5)
                     yield f'<div class="log-success">ok: [localhost] => {{ "msg": "Hello from Sible!" }}</div>'
                     await asyncio.sleep(0.5)
                     yield f'<div class="log-meta">PLAY RECAP ***************************************************************************</div>'
                     yield f'<div class="log-success">localhost                  : ok=2    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0</div>'
                     yield f'<div class="log-success">🏁 Mock Process finished with exit code 0</div>'
                return
            else:
                 yield f'<div class="log-error">❌ Error: Ansible not found and WSL not available.</div>'
                 return
        else:
             yield f'<div class="log-error">❌ Error: ansible-playbook executable not found in PATH.</div>'
             return

        # Prepare the command
        # Parsing logs manually, so we disable ANSI colors to keep text clean
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

            yield f'<div class="log-meta">🚀 Sible: Starting execution of {playbook_name}...</div>'

            # Yield output as it comes
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                # Decode bytes to string, replace null bytes if any
                decoded_line = line.decode('utf-8', errors='replace').rstrip()
                
                # Apply Styling Logic
                css_class = ""
                if "TASK [" in decoded_line or "PLAY [" in decoded_line or "PLAY RECAP" in decoded_line:
                    css_class = "log-meta"
                elif "ok: [" in decoded_line or "ok=" in decoded_line:
                    css_class = "log-success"
                elif "changed: [" in decoded_line or "changed=" in decoded_line:
                    css_class = "log-changed"
                elif "fatal:" in decoded_line or "failed=" in decoded_line or "unreachable=" in decoded_line:
                    css_class = "log-error"
                elif "skipping:" in decoded_line:
                    css_class = "log-debug"
                
                # Wrap in div
                if css_class:
                    formatted_line = f'<div class="{css_class}">{decoded_line}</div>'
                else:
                    formatted_line = f'<div>{decoded_line}</div>'
                
                yield formatted_line

            await process.wait()
            
            exit_class = "log-success" if process.returncode == 0 else "log-error"
            yield f'<div class="{exit_class}">🏁 Sible: Process finished with exit code {process.returncode}</div>'
        
        except Exception as e:
            yield f'<div class="log-error">❌ Sible Error: Failed to start process: {str(e)}</div>'
