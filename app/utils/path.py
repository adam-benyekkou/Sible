import os

def validate_path(path: str) -> str | None:
    """
    Validates if a path:
    1. Exists within the container's filesystem.
    2. Is a directory.
    3. Has read permissions (R_OK).
    
    Returns None if valid, otherwise an error message.
    """
    if not os.path.exists(path):
        return "Path not found"
    
    if not os.path.isdir(path):
        return "Path is not a directory"
    
    if not os.access(path, os.R_OK):
        return "Permission denied (no read access)"
    
    return None
