import subprocess
import os
from pathlib import Path
import logging

logger = logging.getLogger("uvicorn.info")

class GitService:
    @staticmethod
    def _run_git_command(args, cwd, env=None):
        try:
            full_env = os.environ.copy()
            if env:
                full_env.update(env)
                
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                env=full_env
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()
        except FileNotFoundError:
            return False, "Git executable not found."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def pull_playbooks(playbooks_dir: Path, repo_url: str = None, ssh_key: str = None):
        """
        Executes 'git pull' in the playbooks directory.
        Handles SSH key authentication and remote URL updates.
        Returns (success: bool, message: str)
        """
        if not (playbooks_dir / ".git").exists():
            # If repo_url is provided, maybe we should git init and add remote?
            # For now, just return error to be safe.
             if repo_url:
                 # Logic to initialize could go here, but let's stick to "Not a git repo" for safety
                 # or maybe "Cloning..." if empty?
                 pass
             return False, "Not a git repository. Please initialize git in the folder."

        # Update Remote if provided
        if repo_url:
            success, current_url = GitService._run_git_command(["remote", "get-url", "origin"], cwd=playbooks_dir)
            if success and current_url.strip() != repo_url.strip():
                GitService._run_git_command(["remote", "set-url", "origin", repo_url], cwd=playbooks_dir)

        # Prepare SSH Environment
        env = {}
        key_path = None
        
        try:
            if ssh_key:
                import tempfile
                # Create temp file for key. Windows named pipe issue with delete=True? 
                # Use delete=False and manual cleanup.
                fd, key_path = tempfile.mkstemp(text=True)
                with os.fdopen(fd, 'w') as f:
                    f.write(ssh_key)
                    if not ssh_key.endswith('\n'):
                        f.write('\n')
                
                # SSH Command
                # Windows paths in git bash can be tricky. using slash is safer.
                key_path_slash = key_path.replace("\\", "/")
                # StrictHostKeyChecking=no is important for automation
                git_ssh_cmd = f"ssh -i \"{key_path_slash}\" -o StrictHostKeyChecking=no"
                env["GIT_SSH_COMMAND"] = git_ssh_cmd

            success, output = GitService._run_git_command(["pull", "origin", "main"], cwd=playbooks_dir, env=env)
            
            if success:
                if "Already up to date" in output:
                    return True, "Already up to date."
                return True, f"Synced: {output}"
            else:
                return False, f"Git Pull Failed: {output}"

        finally:
            if key_path and os.path.exists(key_path):
                try:
                    os.unlink(key_path)
                except:
                    pass

    @staticmethod
    def get_last_commit(playbooks_dir: Path):
        """
        Returns the last commit hash and message.
        """
        if not (playbooks_dir / ".git").exists():
            return None
            
        success, output = GitService._run_git_command(["log", "-1", "--format=%h - %s (%cr)"], cwd=playbooks_dir)
        return output if success else None
