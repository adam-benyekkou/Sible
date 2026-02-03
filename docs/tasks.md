# Project Tasks & Phases

## Phase 1: Foundation & Project Scaffolding

- [x] **Project Initialization**
  - [x] Create directory structure (`app/`, `templates/`, `static/`, `docs/`)
  - [x] Create detailed documentation (`Idea.md`, `prod.md`, `architecture.md`)
  - [x] Set up Git & `.gitignore`
- [x] **Basic Backend Setup**
  - [x] Install FastAPI & Dependencies (`main.py`)
  - [x] Configure Jinja2 templates
  - [x] Serve static files
- [ ] **UI Skeletons (Dockge Style)**
  - [x] Create `layout.html` (Base template)
  - [x] Create `index.html` (Dashboard view)
  - [x] Implement Sidebar listing of Playbooks

## Phase 2: Core Functionality (Editor & Execution)

- [x] **Playbook Management**
  - [x] Implement File Reader Service (`app/services.py`)
  - [x] API Endpoint to list `.yaml` files
  - [x] API Endpoint to read/write file content
  - [x] API Endpoint to create/delete files (Bonus)
- [ ] **Editor Integration**
  - [ ] Integrate Ace Editor (via CDN or static asset)
  - [ ] Bind Editor to File Content (HTMX/Alpine)
  - [ ] "Save" button functionality
- [ ] **Playbook Execution (The "Runner")**
  - [ ] Create `ansible-runner` wrapper or `asyncio.subprocess` logic
  - [ ] Implement Server-Sent Events (SSE) endpoint for logs
  - [ ] Terminal UI to display streamed logs

## Phase 3: Scheduling & Advanced Features

- [ ] **Scheduler System**
  - [ ] Integrate `APScheduler`
  - [ ] UI for managing schedules (Cron expression input)
  - [ ] Backend logic to trigger jobs
- [ ] **Reliability & Error Handling**
  - [ ] Toast notifications for success/error
  - [ ] Graceful handling of missing files or bad permissions

## Phase 4: Polish & Production

- [ ] **Dockerization**
  - [x] Create `Dockerfile` (with Ansible installed)
  - [x] Create `docker-compose.yml` for easy consumption
- [ ] **UI Polish**
  - [x] Dark mode refinements (Pico.css override)
  - [x] Responsive adjustments (Basic)
- [ ] **Documentation**
  - [ ] Finalize `README.md` with usage instructions
