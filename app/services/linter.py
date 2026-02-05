import shutil
import sys
import asyncio
from pathlib import Path
import tempfile
import json
import os

class LinterService:
    @staticmethod
    async def lint_playbook_content(content: str) -> list:
        # Same logic as before
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
