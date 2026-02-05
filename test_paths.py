import sys
from pathlib import Path
from sqlmodel import Session, create_engine, SQLModel
import os

# Mock settings
class MockSettings:
    PLAYBOOKS_DIR = Path("playbooks").resolve()

# Mock service logic
import re
def validate_path(name: str) -> bool:
    print(f"Validating path: {name}")
    if not re.match(r'^[a-zA-Z0-9_\-\.\/]+$', name):
        print("Regex fail")
        return False
    if not name.endswith((".yaml", ".yml")):
        print("Extension fail")
        return False
    try:
        target_path = (MockSettings.PLAYBOOKS_DIR / name).resolve()
        print(f"Target path: {target_path}")
        print(f"Root path: {MockSettings.PLAYBOOKS_DIR}")
        if not str(target_path).startswith(str(MockSettings.PLAYBOOKS_DIR)):
            print("Startswith check fail")
            return False
        return True
    except Exception as e:
        print(f"Exception: {e}")
        return False

# Test subfolder path
print(f"Result for 'folder/test.yaml': {validate_path('folder/test.yaml')}")

# Create dummy subfolder and file to test .exists()
os.makedirs("playbooks/folder", exist_ok=True)
Path("playbooks/folder/test.yaml").touch()
print(f"Exists check: {Path('playbooks/folder/test.yaml').resolve().exists()}")
