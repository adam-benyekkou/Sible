from fastapi.testclient import TestClient
from app.main import app
from app.services import PlaybookService
import pytest

client = TestClient(app)

@pytest.fixture
def mock_playbooks(monkeypatch):
    # Mock the service methods directly to avoid file system dependency in API tests
    def mock_list():
        return ["test.yaml"]
    
    def mock_get(name):
        if name == "test.yaml":
            return "content"
        return None

    def mock_save(name, content):
        return True

    monkeypatch.setattr(PlaybookService, "list_playbooks", mock_list)
    monkeypatch.setattr(PlaybookService, "get_playbook_content", mock_get)
    monkeypatch.setattr(PlaybookService, "save_playbook_content", mock_save)

def test_sidebar_render(mock_playbooks):
    response = client.get("/partials/sidebar")
    assert response.status_code == 200
    assert "test.yaml" in response.text
    assert 'class="playbook-item"' in response.text

def test_get_editor_view(mock_playbooks):
    response = client.get("/playbook/test.yaml")
    assert response.status_code == 200
    assert "content" in response.text
    assert 'id="editor"' in response.text

def test_get_editor_view_404(mock_playbooks):
    response = client.get("/playbook/missing.yaml")
    assert response.status_code == 200
    assert "File not found" in response.text

def test_save_playbook_api(mock_playbooks):
    response = client.post("/playbook/test.yaml", data={"content": "new content"})
    assert response.status_code == 200
    assert "Saved successfully" in response.text
