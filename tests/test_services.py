import pytest
import asyncio
from app.services import PlaybookService, RunnerService

def test_create_and_list_playbooks(temp_playbooks_dir):
    # 1. List empty
    assert PlaybookService.list_playbooks() == []
    
    # 2. Create 'test.yaml'
    assert PlaybookService.create_playbook("test.yaml") == True
    
    # 3. List contains 'test.yaml'
    listing = PlaybookService.list_playbooks()
    assert len(listing) == 1
    assert listing[0] == 'test.yaml'

def test_prevent_duplicate_creation(temp_playbooks_dir):
    PlaybookService.create_playbook("duplicate.yaml")
    # Try creating again
    assert PlaybookService.create_playbook("duplicate.yaml") == False

def test_read_write_playbook(temp_playbooks_dir):
    name = "content_test.yaml"
    PlaybookService.create_playbook(name)
    
    # Default content usually empty or template
    # Let's write
    new_content = "---\n- name: Test"
    assert PlaybookService.save_playbook_content(name, new_content) == True
    
    # Read back
    read_content = PlaybookService.get_playbook_content(name)
    assert read_content == new_content

def test_delete_playbook(temp_playbooks_dir):
    name = "todelete.yaml"
    PlaybookService.create_playbook(name)
    assert len(PlaybookService.list_playbooks()) == 1
    
    assert PlaybookService.delete_playbook(name) == True
    assert len(PlaybookService.list_playbooks()) == 0

@pytest.mark.asyncio
async def test_runner_service_mock(temp_playbooks_dir):
    # Create a dummy playbook
    name = "mock_run.yaml"
    PlaybookService.create_playbook(name)
    
    # We authenticate that RunnerService.run_playbook is an async generator
    # We won't test the actual subprocess here (complex to mock completely in unit test without shell),
    # but we can verify it handles missing files.
    
    missing_gen = RunnerService.run_playbook("non_existent.yaml")
    # Consume generator
    output = []
    async for line in missing_gen:
        output.append(line)
        
    assert any("not found" in line for line in output)
