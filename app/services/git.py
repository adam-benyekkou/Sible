import subprocess
from pathlib import Path
import logging

logger = logging.getLogger("uvicorn.info")

class GitService:
    @staticmethod
    def _run_git_command(args, cwd):
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()
        except FileNotFoundError:
            return False, "Git executable not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def pull_playbooks(playbooks_dir: Path):
        """
        Executes 'git pull' in the playbooks directory.
        Returns (success: bool, message: str)
        """
        if not (playbooks_dir / ".git").exists():
            return False, "Not a git repository."

        success, output = GitService._run_git_command(["pull"], cwd=playbooks_dir)
        if success:
            # Check if "Already up to date."
            if "Already up to date" in output:
                return True, "Already up to date."
            return True, f"Synced: {output}"
        else:
            return False, f"Git Pull Failed: {output}"

    @staticmethod
    def get_last_commit(playbooks_dir: Path):
        """
        Returns the last commit hash and message.
        """
        if not (playbooks_dir / ".git").exists():
            return None
            
        success, output = GitService._run_git_command(["log", "-1", "--format=%h - %s (%cr)"], cwd=playbooks_dir)
        return output if success else None
