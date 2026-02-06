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

## Phase 11: Template Library (The Blueprints)

Goal: Provide a "Gallery" of best-practice playbooks.

### 11.1 Blueprint Structure & Metadata

- [ ] **Metadata Extraction**: Define a standard where the first few lines of a template contain YAML comments for the UI.
  - *Example*: `# Title: Update Systems`, `# Description: Runs apt update and upgrade.`
- [ ] **Template Service**: Create `app/services/template_service.py`.
  - [ ] `list_templates()`: Scans `/app/blueprints/`, parses the title/description comments, and returns a JSON list.
  - [ ] `get_template_content(filename)`: Returns the raw YAML string.

### 11.2 UI Integration (The "Bridge")

- [ ] **Enhanced New Playbook Modal**:
  - [ ] Add a `<select>` dropdown titled "Start from Blueprint (Optional)".
  - [ ] Populated via `hx-get="/api/templates"` on modal load.
- [ ] **Frontend Logic (Alpine.js/HTMX)**:
  - [ ] When a template is selected, send a request to `GET /api/templates/{name}`.
  - [ ] **Ace Editor Injection**: Use a JavaScript event to push the returned YAML content into the Ace Editor instance immediately.
- [ ] **The "Instantiate" Endpoint**:
  - [ ] `POST /api/playbooks/create-from-template`: Takes `template_name` and `new_filename`.
  - [ ] **Safety Check**: Ensure the new filename doesn't already exist in the `/playbooks` folder.

## Phase 12: Security & Architecture (Production Readiness)

Goal: Secure the application so it can be exposed on a LAN.

- [ ] **Authentication (The Gatekeeper)**
  - [ ] Implement `AuthService` with `passlib` (bcrypt) and `python-jose` (JWT).
  - [ ] Create `POST /auth/login` and a simple `login.html` page (Vercel style).
  - [ ] Secure all API routes (Middleware) to require a valid HttpOnly Cookie.
  - [ ] Create a default admin user on startup if none exists.
- [ ] **Refactoring (Service Layer)**
  - [ ] Crucial: Apply the "Service Layer Pattern" refactor.
  - [ ] Move logic out of `main.py` into `app/services/` and `app/routers/` to ensure the code is readable by others.
- [ ] **Security Hardening (Public Readiness)**
  - [ ] **Secret Scan**: Use `trufflehog` or `git-secrets` to ensure no SSH keys or passwords exist in Git history.
  - [ ] **No Hardcoded Secrets**: Ensure all configuration uses `os.getenv` with no dangerous default values (e.g., `SECRET_KEY`).

## Phase 13: GitOps Lite (The Sync)

Goal: Stop editing code in production. Pull it from GitHub.

- [ ] **Backend: Git Service**
  - [ ] Add `git` to the Dockerfile.
  - [ ] Create endpoint `POST /api/git/pull`.
  - [ ] Implementation: Runs `git pull origin main` inside the `/playbooks` folder.
- [ ] **UI: The Sync Button**
  - [ ] Add a "Sync" or "Pull" button in the Sidebar header.
  - [ ] Show a toast notification: "Updated 3 files from remote."

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
  - [ ] Solution: On first startup, auto-create a `demo-playbook.yml` (e.g., ping) and populate the inventory with `localhost`.
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
  - [ ] Add a `LICENSE` file (MIT for high permissiveness or AGPL v3 for viral open-source enforcement).
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
  - [ ] Create `.github/ISSUE_TEMPLATE/` for Bug Reports and Feature Requests to standardize feedback.
