from sqlmodel import Session, select, text
from app.services.playbook import PlaybookService
from app.services.inventory import InventoryService
from app.services.auth import AuthService
from app.models import Host, User, UserRole, AppSettings
from app.core.config import get_settings
import logging
import os
import random
from pathlib import Path
from datetime import datetime, timedelta

settings = get_settings()
logger = logging.getLogger("uvicorn.info")

WELCOME_PLAYBOOK_NAME = "welcome.yml"
WELCOME_PLAYBOOK_CONTENT = """---
- name: Welcome to Sible
  hosts: all
  gather_facts: false
  tasks:
    - name: Display Welcome Message
      debug:
        msg:
          - "Welcome to Sible v1.0.0"
          - "Professional Ansible Orchestration Made Easy."
          - "Your onboarding is complete. Happy automating!"
"""

ONBOARDING_INVENTORY_NAME = "inventory.ini"
ONBOARDING_INVENTORY_CONTENT = """[all]
local_server ansible_host=127.0.0.1 ansible_connection=local
"""

# Demo inventory content
DEMO_INVENTORY_CONTENT = """[the-front-lines]
spider-web            ansible_host=10.0.1.10  ansible_user=ubuntu
no-internet-explorer  ansible_host=10.0.1.11  ansible_user=ubuntu
captain-404           ansible_host=10.0.1.12  ansible_user=ubuntu
www-are-you           ansible_host=10.0.1.13  ansible_user=ubuntu
error-500-lives-here  ansible_host=10.0.1.14  ansible_user=ubuntu

[the-brain-trust]
data-vader        ansible_host=10.0.2.10  ansible_user=postgres
sir-sql-a-lot     ansible_host=10.0.2.11  ansible_user=postgres
the-big-ledger    ansible_host=10.0.2.12  ansible_user=postgres
lord-of-the-joins ansible_host=10.0.2.13  ansible_user=postgres

[gate-keepers]
steady-eddie      ansible_host=10.0.3.10  ansible_user=admin
wobble-free       ansible_host=10.0.3.11  ansible_user=admin
the-bouncer       ansible_host=10.0.3.12  ansible_user=admin
port-80-and-chill ansible_host=10.0.3.13  ansible_user=admin

[the-watchers]
sauron-sees-all   ansible_host=10.0.4.10  ansible_user=monitor
metric-avengers   ansible_host=10.0.4.11  ansible_user=monitor
alert-fatigue     ansible_host=10.0.4.12  ansible_user=monitor
"""

def seed_users(db: Session):
    """
    Seeds initial users with RBAC roles.
    Idempotent: checks for existence before creating.
    """
    auth_service = AuthService(db)
    users_to_seed = [
        {"username": "admin", "role": UserRole.ADMIN},
        {"username": "operator", "role": UserRole.OPERATOR},
        {"username": "watcher", "role": UserRole.WATCHER},
    ]
    
    for user_data in users_to_seed:
        username = user_data["username"]
        role = user_data["role"]
        
        stmt = select(User).where(User.username == username)
        existing_user = db.exec(stmt).first()
        
        if not existing_user:
            logger.info(f"Seeding user: {username} ({role})")
            # Password matches username for onboarding phase
            auth_service.create_user(username, username, role)
        else:
            logger.debug(f"User {username} already exists, skipping.")

def seed_app_settings(db: Session):
    """
    Seeds initial application settings if not present.
    """
    stmt = select(AppSettings).where(AppSettings.id == 1)
    existing_settings = db.exec(stmt).first()
    
    if not existing_settings:
        logger.info("Seeding AppSettings (favicon/paths)...")
        settings_record = AppSettings(
            id=1,
            app_name="Sible",
            logo_path="/static/img/logo.png",
            favicon_path="/static/img/logo.png",
            playbooks_path=str(settings.PLAYBOOKS_DIR)
        )
        db.add(settings_record)
        db.commit()
    else:
        # Ensure playbooks_path and favicon are correct
        changed = False
        if existing_settings.playbooks_path != str(settings.PLAYBOOKS_DIR):
            existing_settings.playbooks_path = str(settings.PLAYBOOKS_DIR)
            changed = True
        if not existing_settings.favicon_path:
            existing_settings.favicon_path = "/static/img/logo.png"
            changed = True
        
        if changed:
            db.add(existing_settings)
            db.commit()

def seed_onboarding_data(db: Session, playbook_service: PlaybookService):
    """
    Seeds initial data for a fresh installation.
    1. Creates welcome.yml in infrastructure/playbooks.
    2. Creates onboarding.ini in infrastructure/inventory.
    3. Preserves existing Jinja2 templates in infrastructure/templates.
    """
    try:
        infra_dir = settings.INFRASTRUCTURE_DIR
        playbooks_dir = infra_dir / "playbooks"
        inventory_dir = infra_dir / "inventory"
        templates_dir = infra_dir / "templates"

        # Ensure directories exist
        for d in [playbooks_dir, inventory_dir, templates_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 1. Seed welcome.yml if not present
        welcome_path = playbooks_dir / WELCOME_PLAYBOOK_NAME
        if not welcome_path.exists():
            logger.info(f"Seeding {WELCOME_PLAYBOOK_NAME}...")
            welcome_path.write_text(WELCOME_PLAYBOOK_CONTENT, encoding="utf-8")
        
        # 2. Seed onboarding.ini if no hosts in DB
        hosts = db.exec(select(Host)).all()
        if not hosts:
            logger.info("No hosts found in DB. Seeding onboarding inventory...")
            inv_path = inventory_dir / ONBOARDING_INVENTORY_NAME
            
            # Always ensure the local_server is present in the file if DB is empty
            inv_path.write_text(ONBOARDING_INVENTORY_CONTENT, encoding="utf-8")
            
            # Sync to DB (this imports from the file we just wrote)
            InventoryService.import_ini_to_db(db, content=ONBOARDING_INVENTORY_CONTENT)

        # 3. Template Preservation (Implicit by mkdir if not exists, but we can log)
        existing_templates = list(templates_dir.glob("*.j2"))
        if existing_templates:
            logger.info(f"Found {len(existing_templates)} existing Jinja2 templates. Preserving.")
        else:
            logger.info("No existing Jinja2 templates found in infrastructure/templates.")

    except Exception as e:
        logger.error(f"Onboarding seeding failed: {e}")


def seed_demo_data(db: Session):
    """
    Seeds demo data for demonstration purposes.
    This includes fake hosts, inventory, and job history.
    Only runs when DEMO_MODE is enabled.
    """
    if not settings.DEMO_MODE:
        return
    
    logger.info("Seeding demo data...")
    
    # 0. Force wipe existing data to prevent duplicates across restarts
    from app.models import Host, JobRun, FavoriteServer
    db.exec(select(Host)).all() # Ensure metadata is loaded
    db.execute(text("DELETE FROM host"))
    db.execute(text("DELETE FROM jobrun"))
    db.execute(text("DELETE FROM favoriteserver"))
    db.commit()
    
    # 1. Create demo user if not exists
    auth_service = AuthService(db)
    demo_user = db.exec(select(User).where(User.username == "demo")).first()
    if not demo_user:
        logger.info("Creating demo user...")
        auth_service.create_user("demo", "demo", UserRole.ADMIN)
        demo_user = db.exec(select(User).where(User.username == "demo")).first()
    
    # 2. Seed demo inventory
    # In demo mode, we force re-seed to ensure all servers are present
    logger.info("Syncing demo inventory...")
    # Import demo inventory to DB
    InventoryService.import_ini_to_db(db, content=DEMO_INVENTORY_CONTENT)
    
    # Update host statuses to simulate online servers
    demo_hosts = db.exec(select(Host)).all()
    for host in demo_hosts:
        if host.status == "unknown" or not host.latency:
            host.status = "online"
            host.latency = float(random.randint(5, 50))
    db.add_all(demo_hosts)
    db.commit()
    
    # 3. Seed demo job history
    from app.models import JobRun
    existing_jobs = db.exec(select(JobRun)).all()
    if not existing_jobs:
        logger.info("Seeding demo job history...")
        demo_playbooks = [
            "deploy_webapp.yaml",
            "system_health.yaml",
            "backup.yaml",
            "update_packages.yaml"
        ]
        
        # Create fake job runs
        now = datetime.utcnow()
        statuses = ["success", "success", "success", "failed"]
        
        for i, playbook in enumerate(demo_playbooks):
            for j in range(3):  # 3 runs per playbook
                start_time = now - timedelta(days=j*2, hours=i*2)
                end_time = start_time + timedelta(minutes=random.randint(1, 10))
                
                job = JobRun(
                    playbook=playbook,
                    username="demo",
                    status=statuses[i % len(statuses)],
                    start_time=start_time,
                    end_time=end_time,
                    extra_vars="{}",
                    tags="",
                    limit="",
                    stdout=f"PLAYBOOK EXECUTION: {playbook}\n" + "TASK [Gathering Facts] ok: [1]\n"*3 + "TASK [Complete] changed: [1]\n"*2 + "PLAY RECAP \nlocalhost : ok=3    changed=2    unreachable=0    failed=0\n"
                )
                db.add(job)
        
        db.commit()
    
    logger.info("Demo data seeding complete.")



