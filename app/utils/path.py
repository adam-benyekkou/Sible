import os
from pathlib import Path

def validate_directory_path(path: str, root_jail: str = "/") -> str | None:
    """
    Validates if a path:
    1. Is strictly within the root_jail directory.
    2. Exists within the container's filesystem.
    3. Is a directory.
    4. Has read permissions (R_OK).
    
    Returns None if valid, otherwise an error message.
    """
    try:
        abs_root = Path(root_jail).resolve()
        abs_path = Path(path).resolve()
        
        # Security: Enforce jail
        if not str(abs_path).startswith(str(abs_root)):
             return f"Security Error: Path must be within {root_jail}"

        if not abs_path.exists():
            return "Path not found"
        
        if not abs_path.is_dir():
            return "Path is not a directory"
        
        if not os.access(str(abs_path), os.R_OK):
            return "Permission denied (no read access)"
        
        return None
    except Exception as e:
        return f"Validation Error: {str(e)}"
