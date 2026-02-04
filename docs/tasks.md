# Project Tasks & Roadmap

## Phase 1: Foundation & Project Scaffolding (Completed)

- [x] **Project Initialization**
  - [x] Create directory structure (`app/`, `templates/`, `static/`, `docs/`)
  - [x] Create detailed documentation (`Idea.md`, `prod.md`, `architecture.md`)
  - [x] Set up Git & `.gitignore`
- [x] **Basic Backend Setup**
  - [x] Install FastAPI & Dependencies (`main.py`)
  - [x] Configure Jinja2 templates
  - [x] Serve static files
- [x] **UI Skeletons (Dockge Style)**
  - [x] Create `layout.html` (Base template)
  - [x] Create `index.html` (Dashboard view)
  - [x] Implement Sidebar listing of Playbooks

## Phase 2: Core Functionality (Completed)

- [x] **Playbook Management**
  - [x] Implement File Reader Service (`app/services.py`)
  - [x] API Endpoint to list `.yaml` files
  - [x] API Endpoint to read/write file content
  - [x] API Endpoint to create/delete files (Bonus)
- [x] **Editor Integration**
  - [x] Integrate Ace Editor (via CDN or static asset)
  - [x] Bind Editor to File Content (HTMX/Alpine)
  - [x] "Save" button functionality
- [x] **Playbook Execution (The "Runner")**
  - [x] Create `ansible-runner` wrapper or `asyncio.subprocess` logic
  - [x] Implement Server-Sent Events (SSE) endpoint for logs
  - [x] Terminal UI to display streamed logs

## Phase 2.5: Reliability & Quality Assurance (Completed)

- [x] **Reliability**
  - [x] Toast notifications for success/error
  - [x] Graceful handling of missing files or bad permissions
- [x] **Unit Testing**
  - [x] Set up `pytest` and `httpx`
  - [x] Test `PlaybookService` (CRUD)
  - [x] Test `RunnerService` (Mocking asyncio.subprocess)
  - [x] Test API Routes (`TestClient`)

## Phase 3: Automation (The Scheduler)

Goal: Transform the tool into an Orchestrator.

- [x] **Scheduler Backend**
  - [x] Install APScheduler.
  - [x] Configure SQLite job store (so schedules survive restarts).
- [x] **Scheduling UI**
  - [x] Add a "Schedule" button in the Playbook toolbar.
  - [x] Create a modal to accept Cron expressions (e.g., `0 3 * * *`).
- [x] **The Queue View**
  - [x] Create a "Rituals" or "Queue" page listing upcoming jobs.
  - [x] Display "Next Run" countdowns.

## Phase 4: Production Packaging & History

Goal: Deployable on K3s with Persistence.

- [ ] **Dockerization**
  - [x] Write Dockerfile based on `python:3.11-slim`.
  - [ ] CRITICAL: Install `ansible-core`, `sshpass`, and `openssh-client` via apt/pip.
  - [ ] Set up volume mount points for `/playbooks` and `/root/.ssh`.
- [ ] **Job History (The "Memory")**
  - [ ] **Database**: Create `sible.db` with `JobRun` model (id, playbook, status, time, log, exit_code).
  - [ ] **Backend**: Refactor `run_playbook` to save "Running" -> "Success/Failed" states and logs.
  - [ ] **Frontend**: Add History icon in sidebar and History View/Modal with logs.

## Phase 5: Observability

Goal: "Day 2 Operations" - Status Monitoring.

- [ ] **Status Indicators**
  - [ ] Update Sidebar icons based on last run status (Green Dot = Success, Red Dot = Failed).

## Phase 6: Settings & Integrations (Dockge Parity)

- [ ] **Settings Infrastructure**
  - [ ] Create a `settings.json` file (or SQLite table) to store app config.
  - [ ] Create a Settings View with Tabs (General, Git, Notifications).

- [ ] **GitOps Integration**
  - [x] Add `git` to Dockerfile (Already present).
  - [ ] Backend: Create service to run `git pull`.
  - [ ] Frontend: "Sync Now" button in settings.

- [ ] **Notification System (Apprise)**
  - [ ] Install `apprise` (Python library).
  - [ ] **Strategy**: Use Apprise URLs (e.g., `discord://webhook_id/token`) to support 50+ services (SMS, Telegram, Email) with minimal code. Do NOT implement native APIs manually.
  - [ ] Create logic: If Playbook exit_code != 0 -> Send Apprise notification.
  - [ ] UI: Form to add a generic "Apprise URL" (supports all providers).

- [ ] **SSH Key Management**
  - [ ] UI: Textarea to paste a Private Key.
  - [ ] Backend: Write key to `/root/.ssh/id_rsa` and fix permissions (0600).

## Phase 7: Environment Management (The Target)

Goal: Manage remote servers and secrets securely.

- [ ] **Inventory Editor**
  - [ ] Create a UI to edit `inventory.ini` or hosts file.
  - [ ] Add a "Ping Test" button to verify SSH connectivity to hosts.
- [ ] **Secrets Manager**
  - [ ] Create a UI for "Environment Variables" (stored in a secure `.env` or internal dict).
  - [ ] Inject these variables into the `ansible-playbook` process environment.
- [ ] **Galaxy Support**
  - [ ] Detect `requirements.yml`.
  - [ ] Add button "Install Roles" running `ansible-galaxy install`.

## Phase 8: Security & Polish

Goal: Enterprise readiness.

- [ ] **Concurrency Control**
  - [ ] Implement a Python Lock to prevent running the same playbook twice simultaneously.
- [ ] **Dry Run Mode**
  - [ ] Add a yellow "Check" button running `ansible-playbook --check`.
- [ ] **Basic Auth**
  - [ ] Implement a simple login screen (Admin/Password) using FastAPI Security.
