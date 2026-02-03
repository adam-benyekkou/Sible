import pytest
from pathlib import Path
from app.services import PlaybookService

# Use a temporary directory for tests
@pytest.fixture
def mock_playbooks_dir(tmp_path, monkeypatch):
    """
    Redirects PLAYBOOKS_DIR to a temporary directory for isolation.
    """
    monkeypatch.setattr("app.services.PLAYBOOKS_DIR", tmp_path)
    return tmp_path

def test_list_playbooks_empty(mock_playbooks_dir):
    assert PlaybookService.list_playbooks() == []

def test_list_playbooks_with_files(mock_playbooks_dir):
    (mock_playbooks_dir / "test1.yaml").touch()
    (mock_playbooks_dir / "test2.yml").touch()
    (mock_playbooks_dir / "ignore.txt").touch()
    
    playbooks = PlaybookService.list_playbooks()
    assert "test1.yaml" in playbooks
    assert "test2.yml" in playbooks
    assert "ignore.txt" not in playbooks
    assert len(playbooks) == 2

def test_save_and_get_playbook(mock_playbooks_dir):
    name = "new_playbook.yaml"
    content = "- name: Test"
    
    # Save
    assert PlaybookService.save_playbook_content(name, content) is True
    
    # Verify file exists
    assert (mock_playbooks_dir / name).exists()
    
    # Get
    read_content = PlaybookService.get_playbook_content(name)
    assert read_content == content

def test_save_invalid_extension(mock_playbooks_dir):
    assert PlaybookService.save_playbook_content("bad.txt", "content") is False
    assert not (mock_playbooks_dir / "bad.txt").exists()
