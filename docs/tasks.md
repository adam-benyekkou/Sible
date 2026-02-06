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

- [x] **Dockerization**
  - [x] Write Dockerfile based on `python:3.11-slim`.
  - [x] CRITICAL: Install `ansible-core`, `sshpass`, and `openssh-client` via apt/pip.
  - [x] Set up volume mount points for `/playbooks` and `/root/.ssh`.
- [x] **Job History (The "Memory")**
  - [x] **Database**: Create `sible.db` with `JobRun` model (id, playbook, status, time, log, exit_code).
  - [x] **Backend**: Refactor `run_playbook` to save "Running" -> "Success/Failed" states and logs.
  - [x] **Frontend**: Add History icon in sidebar and History View/Modal with logs.

## Phase 5: Observability

Goal: "Day 2 Operations" - Status Monitoring.

- [x] **Status Indicators**
  - [x] Update Sidebar icons based on last run status (Green Dot = Success, Red Dot = Failed).

## Phase 6: Settings & Integrations (Dockge Parity)

- [x] **UI Architecture**
  - [x] Create `/settings` page with Sidebar Layout (General, Notifications).
  - [x] **General**: Move "Max Log Count" & "Retention Days" input here.
  - [x] **Notifications**: Section for Apprise URL.

- [x] **Backend: Settings Store**
  - [x] Create `Settings` model (Singleton or table).
  - [x] Fields: `apprise_url`, `notify_on_success`, `notify_on_failure`.
  - [x] endpoints: `GET /api/settings`, `POST /api/settings`.

- [x] **Notification Engine (Apprise)**
  - [x] Install `apprise`.
  - [x] Create `send_notification(message, status)`.
  - [x] Hook into Runner:
    - [x] If status=failed & notify_on_failure -> Alert.
    - [x] If status=success & notify_on_success -> Alert.

- [x] **Frontend Details**
  - [x] Add "Test" button for fake notification.
  - [x] Use password input for Apprise URL.

## Phase 7: Environment Management (The Target)

Goal: Manage remote servers and secrets securely.

- [x] **Inventory Editor**
  - [x] Create a UI to edit `inventory.ini` or hosts file.
  - [x] Add a "Ping Test" button to verify SSH connectivity to hosts.
- [x] **Secrets Manager**
  - [x] Create a UI for "Environment Variables" (stored in a secure `.env` or internal dict).
  - [x] Inject these variables into the `ansible-playbook` process environment.
- [x] **Galaxy Support**
  - [x] Detect `requirements.yml`.
  - [x] Add button "Install Roles" running `ansible-galaxy install`.

- [x] **Sidebar Hierarchy**
  - [x] Recursive folder scanning in `PlaybookService`.
  - [x] Collapsible folder UI (`<details>`/`<summary>`) in sidebar.
  - [x] Recursive Jinja2 macro for deep nesting.
  - [x] CSS styling for nested folders and files.
  - [x] Support for saving/creating files in subdirectories.

## Phase 8: Docker Transition & Execution (Completed)

- [x] Revert to stable Phase 6 state (Git Reset)
- [x] Restore Refined UI & Fixes (Manual Re-application)
- [x] Transition to Docker Execution
  - [x] Identify Docker necessity for stable Ansible environment
  - [x] Start Docker Desktop daemon
  - [x] Build and start containers with `docker-compose`
  - [x] Verify Ansible execution inside Docker

- [x] **Playbook Cancellation**
  - [x] Implement process tracking in `RunnerService`.
  - [x] Create API endpoint for stopping a playbook.
  - [x] Add "Stop" button to terminal UI.

## Phase 9: Interactive Execution (The Launchpad) (Completed)

- [x] **Pre-flight Configuration**
  - [x] Define `params` field in `JobRun` model for parameter auditing.
  - [x] Implement `<dialog>` modal UI for dynamic run configuration.
  - [x] Support for `--limit`, `--tags`, and Verbosity levels.
- [x] **Dynamic Variable Injection**
  - [x] Create reactive Alpine.js builder for extra variables (`-e`).
- [x] **Visual Polish**
  - [x] Global Rocket Purge (Removed 🚀 while preserving status dots/arrows).
  - [x] Update `RunnerService` to sanitize and inject JSON-encoded extra vars.
- [x] **Audit & History**
  - [x] Record specific execution parameters for every job run.
  - [x] Display "(Custom)" badge in history view with parameter tooltips.

## Phase 10: Visual Dashboard (The "Dockge" Home)

Goal: Replace the generic "Welcome" page with a live monitoring grid. This is the visual identity of Sible.

- [x] **Backend: Status API**
  - [x] Create `GET /api/dashboard/stats`: Returns simple metrics (Total Playbooks, Success Rate %, Total Hosts).
  - [x] Optimize the `ping_hosts` function to be called periodically via HTMX or polling.
- [x] **Frontend: The Server Grid**
  - [x] Redesign `/inventory`: Move from a simple list to a Grid of Cards.
  - [x] Card UI: Hostname, OS Icon (optional), and the massive Status Dot (Green/Red).
  - [x] Home Page Integration: Make this Grid the default view on `index.html`.
- [x] **Interactivity**
  - [x] Add "Refresh Status" button (triggers background ping).
  - [x] Add "Terminal" button on cards (optional placeholder for now).

- [x] **Phase 10.2: Advanced Inventory & Secrets (Completed)**
  - [x] **Database Implementation**: Transitioned to SQLAlchemy-backed storage with full CRUD.
  - [x] **Bi-directional Sync**: Implemented `inventory.ini` <-> Database synchronization (Source of truth: DB, with Raw Editor fallback).
  - [x] **Secrets Integration**: Native support for referencing `EnvVar` secrets (SSH Key/Password) with UI dropdowns.
  - [x] **Connection Validation**: Automated Ansible-ping check during host registration.

### 10.3 Visual Dashboard (Monitoring Hub) [COMPLETED]

- [x] **Heartbeat Utility**: Created `app/utils/network.py` with an async `check_ssh(ip, port)`.
- [x] **Background Worker**: Configured a recurring scheduler task to refresh statuses every 2 minutes.
- [x] **The Server Card UI**: Implemented `templates/components/server_card.html` with CSS pulse animations.
- [x] **Global Health Header**: Integrated real-time stats and health progress bar in the main dashboard.
- [x] **Terminal UX**: Renamed button to `>_` and added toast notifications for connection failures.

## Phase 11: Template Library (The Blueprints) (Completed)

Goal: Provide a "Gallery" of best-practice playbooks.

### 11.1 Blueprint Structure & Metadata

- [x] **Metadata Extraction**: Define a standard where the first few lines of a template contain YAML comments for the UI.
  - *Example*: `# Title: Update Systems`, `# Description: Runs apt update and upgrade.`
- [x] **Template Service**: Create `app/services/template.py`.
  - [x] `list_templates()`: Scans `/app/blueprints/`, parses the title/description comments, and returns a JSON list.
  - [x] `get_template_content(filename)`: Returns the raw YAML string.
- [x] **Template Dashboard (Manager)**
  - [x] CRUD Interface for Templates (`templates/templates_index.html`).
  - [x] Table Layout with Edit/Delete actions.
  - [x] Title & Filename separation in Editor.

### 11.2 UI Integration (The "Bridge")

- [x] **Enhanced New Playbook Modal**:
  - [x] Add a `<select>` dropdown titled "Start from Template".
  - [x] Populated templates via API.
- [x] **Frontend Logic (Alpine.js)**:
  - [x] Fetch template content and inject into editor.
- [x] **Subdirectory Support**:
  - [x] Allow creating playbooks in subfolders (e.g., `web/nginx.yml`).
- [x] **The "Instantiate" Flow**:
  - [x] Create Playbook from Template content.
  - [x] **Safety Check**: Ensure filename doesn't collide.

## Phase 12: Security & Architecture (Production Readiness)

Goal: Secure the application so it can be exposed on a LAN.

### 12.1 The "Gatekeeper" (Authentication)

Goal: Move from an open access to a secure multi-user platform.

- [x] **User Model & DB Migration**
  - [x] Update SQLAlchemy models to include a User table: `id`, `username`, `hashed_password`, `role` (Admin/Operator/Watcher).
- [x] **Auth Service (`app/services/auth.py`)**
  - [x] Implement `verify_password` and `get_password_hash` using passlib (bcrypt).
  - [x] Implement login logic and session handling.
- [x] **Authentication Flow**
  - [x] `POST /api/auth/login`: Validates credentials.
  - [x] `GET /login`: Minimalist UI using Pico.css.
  - [x] `GET /api/auth/logout`: Clears the session.
- [x] **Middleware / Dependencies**
  - [x] Create a `get_current_user` dependency to protect all sensitive routers.

### 12.2 RBAC (Role-Based Access Control)

Goal: Enforce permissions based on the 3 roles defined.

- [x] **Permission Decorator**
  - [x] Create a `requires_role(role_name)` dependency.
- [x] **Access Logic**
  - [x] **Watcher**: Only GET requests (Dashboard, Inventory, Logs).
  - [x] **Operator**: GET + POST /run (Can execute but not change code/inventory).
  - [x] **Admin**: Full CRUD + Settings + User Management.
- [x] **UI Masking**
  - [x] Update Jinja2 templates to hide buttons (Save, Delete, Run) if the current user lacks permissions.
  - [x] Restrict Settings pages: Watcher only sees Inventory & Retention.
  - [x] Allow users creation, deletion, edit and assign them roles (only Admin can create users)

### 12.3 Service Layer Refactor (The "Clean Code" Move)

Goal: Decouple business logic from route definitions to ensure maintainability.

- [x] **Router Extraction**
  - [x] Move all app routes into specific files: `app/routers/playbooks.py`, `app/routers/inventory.py`, `app/routers/auth.py`.
- [x] **Service Consolidation**
  - [x] Ensure `main.py` is strictly for app initialization.
- [x] **Global Config**
  - [x] Create `app/config.py` using Pydantic Settings.

- [x] **Security Hardening (Public Readiness)**
  - [x] **No Hardcoded Secrets**: Ensure all configuration uses environment variables.

### 12.4 Interactive Terminal (The Live Session) [COMPLETED]

Goal: Add a live terminal to access servers directly from Sible.

- [x] **UI Integration**:
  - [x] Add "Terminal" button to server cards.
  - [x] Create terminal modal with xterm.js.
- [x] **Backend Implementation**:
  - [x] Implement WebSocket-based SSH proxy using `asyncssh`.
  - [x] Handle terminal resizing and interactive input.

## Phase 13: GitOps Lite (The Sync)

Goal: Bridge the gap between Infrastructure as Code (IaC) and your UI.

- [ ] **GitService Implementation (`app/services/git_service.py`)**:
  - [ ] Create a method `pull_playbooks()` that executes `git pull origin main` in the playbooks directory.
  - [ ] Add error handling to detect if the directory isn't a Git repo yet and return a specific error.
  - [ ] **The "SSH Challenge"**: Ensure the Docker container has the host's `~/.ssh/known_hosts` and keys mounted so it can talk to GitHub/GitLab without interactive prompts.

- [ ] **The Sync API**:
  - [ ] `POST /api/git/sync`: Triggers the pull and returns a list of changed files (using `git diff --name-only`).

- [ ] **UI Integration**:
  - [ ] Add a "Sync" button in the Sidebar header (Cloud icon).
  - [ ] Add a "Last Synced" timestamp in the footer or sidebar.
  - [ ] Trigger a Sidebar refresh (HTMX) after a successful pull to show new files.

## Phase 14: Release Engineering (The Launch)

Goal: Automate the distribution so people can `docker run` it.

- [ ] **Docker Optimization & Public Distribution**
  - [ ] Ensure the Dockerfile uses a specific, non-root user for running the app, while keeping root capability for Ansible if needed (or use `sudo`).
  - [ ] Finalize the `docker-compose.yml` for public consumption.
- [ ] **CI/CD & Multi-Arch Pipeline**
  - [ ] Create `.github/workflows/release.yml`.
  - [ ] **Multi-Arch Build**: Build for `amd64` (Servers) AND `arm64` (Raspberry Pi/Apple Silicon).
  - [ ] **Registry**: Push to GitHub Container Registry (`ghcr.io`).
  - [ ] **Semantic Tagging**: Use version tags (`v1.0.0`) instead of just `latest` to avoid breaking production environments.
  - [ ] Steps:
    - [ ] Run Tests (`pytest`).
    - [ ] Build and Push Docker Image.

## Phase 15: The "Day 1" Experience (The Final Touch)

Goal: Elevate the project from a "basic tool" to a "SaaS-grade" application with polish and care.

- [ ] **Onboarding (First Launch)**
  - [ ] Problem: Fresh stalls display an empty dashboard.
  - [ ] Solution: On first startup, auto-create a `demo-playbook.yml` (e.g., ping) and populate the inventory with `localhost` the PC not the docker container localhost.
- [ ] **"Empty State" Design**
  - [ ] Problem: A dashboard with no playbooks looks broken.
  - [ ] Solution: Add aesthetic "Empty State" messages: "No playbooks here. Create one or use a template!" with a clean SVG illustration.
- [ ] **Mobile Responsiveness (The Handheld Check)**
  - [ ] Problem: UI breaks on mobile (buttons off-screen, etc.).
  - [ ] Solution: Implement CSS media queries and a hamburger menu for mobile accessibility.
- [ ] **Branding & Favicon**
  - [ ] Problem: Tab icon is missing or default.
  - [ ] Solution: Add the "S" (Sible) logo as `favicon.ico` and in the header. Add version `v1.0.0` to the sidebar footer.

## Phase 16: The Open Source Pack (Essentials)

Goal: Build trust and enable community contributions for the public release.

- [ ] **Licensing**
  - [x] Add a `LICENSE` file (MIT for high permissiveness or AGPL v3 for viral open-source enforcement).
- [ ] **The "Sale" README**
  - [ ] Create a high-quality `README.md` with:
    - [ ] Demo GIF/Video (Sible in action).
    - [ ] "One-Liner" Docker Compose to get started instantly.
    - [ ] Feature list ("Why Sible?").
- [ ] **Contribution Guidelines**
  - [ ] Create `CONTRIBUTING.md` explaining:
    - [ ] Development environment setup (`pip install -r requirements.txt`).
    - [ ] How to run the test suite.
- [ ] **GitHub Templates**
  - [x] Create `.github/ISSUE_TEMPLATE/` for Bug Reports and Feature Requests to standardize feedback.
