# Sible
>
> A modern, reactive UI for Ansible Playbooks. Inspired by Dockge.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Status](https://img.shields.io/badge/status-wip-orange.svg)

**Note: This project is currently a Work in Progress.**

**Sible** is a lightweight, self-hosted Web UI to manage, edit, and run Ansible playbooks. It is designed to be a "no-build" alternative to complex tools like AWX/Tower, focusing on simplicity and a great user experience for homelabbers and DevOps engineers.

---

## Features

- **Reactive UI**: Built with HTMX and Alpine.js for a snappy, app-like feel without the bloat.
- **Playbook Management**: Create, edit, and delete playbooks directly in the browser.
- **Advanced Editor**: Integrated Ace Editor with custom theme, line numbers, and syntax highlighting.
- **Ansible Linting**: Real-time code quality checks and annotations directly in the editor.
- **Execution & Logs**: Run playbooks manually or headless. View real-time output streams via SSE.
- **Concurrency Control**: Prevents simultaneous execution of the same playbook.
- **Dry Run Mode**: "Check" button to simulate playbook runs without making changes.
- **Job History**: Tracks all manual and scheduled runs with full log retention.
- **Retention Policy**: Advanced retention settings with support for nested playbooks (folder structure).
- **Custom Branding**: Upload your own Logo and Favicon via the UI.
- **Scheduling**: Built-in Cron scheduler with Queue management.
- **Status Indicators**: Visual feedback (Green/Red dots) in the sidebar for the last run status.
- **Custom Playbook Path**: Define an absolute path for playbooks, ideal for mounting external repositories into Docker.
- **Single Container**: Deploys as a single Docker container using SQLite.

## Authentication (Optional)

Sible includes an optional authentication system to protect your instance.

- **Toggleable**: Enable or disable login via **Settings > General > Security**.
- **Secure**: Passwords are stored using secure **BCrypt** hashing.
- **Session Management**: Secure cookie-based sessions with handled redirects for HTMX interactions.

## Tech Stack

- **Backend**: FastAPI (Python), SQLModel (SQLite), APScheduler, Ansible Core
- **Frontend**: Jinja2, HTMX, Alpine.js, Ace Editor, Pico.css
- **Infrastructure**: Docker

## Quick Start

### 1. With Docker Compose (Recommended)

Create a `docker-compose.yml` file:

```yaml
services:
  sible:
    image: sible:latest
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./playbooks:/playbooks
      - ./data:/app/data
      - ~/.ssh:/root/.ssh:ro # Mount SSH keys for Ansible
    environment:
      - SIBLE_SECRET_KEY=change_me
```

Run it:

```bash
docker-compose up -d --build
```

Visit <http://localhost:8000>

### 2. Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

### 3. Custom Playbooks Path

If you mount an external directory into the container (e.g., via Docker volumes), you can configure Sible to look for playbooks in that specific path.

1. Go to **Settings > General**.
2. Locate the **Infrastructure Configuration** section.
3. Enter the absolute path within the container (e.g., `/mnt/infrastructure/playbooks`).
4. Sible will validate the path in real-time.
5. Click **Save General Settings**.

## Directory Structure

Mount your existing playbooks folder to `/app/playbooks` (default) or any custom path of your choice.

```text
/playbooks
  ├── deploy-web.yaml
  ├── update-db.yaml
  └── maintenance.yaml
```
