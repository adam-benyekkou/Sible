from pathlib import Path
import os

# Simulate app/config.py BASE_DIR calculation
base_dir = Path(__file__).resolve().parent.parent
playbooks_dir = base_dir / "playbooks"

print(f"Original playbooks_dir: {playbooks_dir}")
print(f"Resolved playbooks_dir: {playbooks_dir.resolve()}")

# Test startswith
target = (playbooks_dir / "folder" / "test.yaml").resolve()
root = playbooks_dir.resolve()

print(f"Target: {target}")
print(f"Root: {root}")
print(f"Cased match: {str(target).startswith(str(root))}")
print(f"Lower match: {str(target).lower().startswith(str(root).lower())}")
