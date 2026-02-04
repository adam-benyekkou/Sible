import pytest
import json
from app.services import PlaybookService

def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Sible" in response.text

def test_sidebar_partial(client, temp_playbooks_dir):
    response = client.get("/partials/sidebar")
    assert response.status_code == 200
    # Should say "No playbooks found" or similar if empty
    assert "playbooks" in response.text or "No playbooks" in response.text

def test_create_playbook_api(client, temp_playbooks_dir):
    # HTMX request with HX-Prompt header
    headers = {"HX-Prompt": "api_test.yaml"}
    response = client.post("/playbook", headers=headers)
    
    assert response.status_code == 200
    
    # Check Headers for Toast
    assert "HX-Trigger" in response.headers
    trigger_data = json.loads(response.headers["HX-Trigger"])
    
    assert "show-toast" in trigger_data
    assert trigger_data["show-toast"]["level"] == "success"
    assert "created" in trigger_data["show-toast"]["message"]

def test_create_playbook_invalid_api(client, temp_playbooks_dir):
    # Empty name
    headers = {"HX-Prompt": ""}
    response = client.post("/playbook", headers=headers)
    
    # We return 200 for HTMX to show toast, but toast should be error
    assert response.status_code == 200
    
    trigger_data = json.loads(response.headers["HX-Trigger"])
    assert trigger_data["show-toast"]["level"] == "error"

def test_delete_playbook_api(client, temp_playbooks_dir):
    # Create first
    client.post("/playbook", headers={"HX-Prompt": "delete_me.yaml"})
    
    response = client.delete("/playbook/delete_me.yaml")
    assert response.status_code == 200
    
    trigger_data = json.loads(response.headers["HX-Trigger"])
    assert "deleted" in trigger_data["show-toast"]["message"]

def test_stream_endpoint_structure(client, temp_playbooks_dir):
    # Just checking if headers are correct for SSE
    client.post("/playbook", headers={"HX-Prompt": "stream_test.yaml"})
    
    response = client.get("/stream/stream_test.yaml")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

def test_get_editor_view(client, temp_playbooks_dir):
    PlaybookService.create_playbook("view_test.yaml")
    response = client.get("/playbook/view_test.yaml")
    assert response.status_code == 200
    assert "view_test.yaml" in response.text

def test_save_playbook_api(client, temp_playbooks_dir):
    PlaybookService.create_playbook("save_test.yaml")
    response = client.post("/playbook/save_test.yaml", data={"content": "saved content"})
    assert response.status_code == 200
    # Search for toast or success message
    # Based on test_main.py it expects "Saved successfully"
    assert "Saved successfully" in response.text or "saved" in response.text.lower()
    
    # Verify content
    assert PlaybookService.get_playbook_content("save_test.yaml") == "saved content"
