from sqlmodel import Session, select
from app.services.playbook import PlaybookService
from app.services.inventory import InventoryService
from app.models import Host
import logging

logger = logging.getLogger("uvicorn.info")

DEMO_PLAYBOOK_NAME = "hello-sible.yml"
DEMO_PLAYBOOK_CONTENT = """---
- name: Hello Sible
  hosts: all
  gather_facts: false
  tasks:
    - name: Ping
      ping:

    - name: Print Message
      debug:
        msg: "Welcome to Sible! Your automation journey starts here."
"""

def seed_onboarding_data(db: Session, playbook_service: PlaybookService):
    """
    Seeds initial data for a fresh installation.
    1. Creates a demo playbook if no playbooks exist.
    2. Adds localhost to inventory if inventory is empty.
    """
    try:
        # 1. Check Playbooks
        playbooks = playbook_service.list_playbooks()
        if not playbooks:
            logger.info("No playbooks found. Seeding 'hello-sible.yml'...")
            playbook_service.save_playbook_content(DEMO_PLAYBOOK_NAME, DEMO_PLAYBOOK_CONTENT)
        
        # 2. Check Inventory in DB
        hosts = db.exec(select(Host)).all()
        if not hosts:
            logger.info("No hosts found in DB. Checking inventory.ini...")
            content = InventoryService.get_inventory_content()
            
            # If inventory.ini is effectively empty or just has the default header
            if not content or content.strip() == "[all]":
                logger.info("Seeding default localhost inventory...")
                InventoryService.save_inventory_content("[all]\nlocalhost ansible_connection=local\n")
                # Trigger sync to DB
                InventoryService.import_ini_to_db(db)
            else:
                # If INI has content but DB is empty, sync it
                logger.info("Inventory.ini found but DB is empty. Syncing...")
                InventoryService.import_ini_to_db(db)

    except Exception as e:
        logger.error(f"Onboarding seeding failed: {e}")
