import pytest
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.services import PlaybookService

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def temp_playbooks_dir(tmp_path):
    """
    Creates a temporary directory for playbooks and patches the service to use it.
    """
    # Create the dir
    test_dir = tmp_path / "playbooks"
    test_dir.mkdir()
    
    # Patch the global variable in services
    # Note: We must patch where it is USED, or the object itself if simpler.
    # Since specific mapping might be hard, we can just monkeypatch the class attribute if we had one,
    # or better, simple patch 'app.services.PLAYBOOKS_DIR'
    
    with patch("app.services.PLAYBOOKS_DIR", test_dir):
        yield test_dir

# Async support configuration
@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
