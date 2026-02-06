# Sible: Ansible Playbook Manager

## Project Overview

Sible is a modern, lightweight Web UI designed to manage, edit, schedule, and run Ansible Playbooks. It aims to provide a "reactive" desktop-app feel using lightweight web technologies, avoiding the weight of complex frameworks like React or Angular for this specific use case.

## Philosophy

- **Simplicity:** No build steps for the frontend. No complex state management libraries.
- **Reference:** Heavily inspired by "Dockge" (by Louis Lam) in terms of UI layout and philosophy.
- **Performance:** Fast, server-side rendered HTML with HTMX, interactive bits with Alpine.js.

## Tech Stack

- **Backend:** Python 3.11+ (FastAPI)
- **Frontend Logic:** HTMX (Server interactions) + Alpine.js (Client state/Tabs)
- **Styling:** Pico.css (Dark mode) + Custom CSS
- **Editor:** Ace Editor
- **Task Runner:** `ansible-runner` or `asyncio.subprocess`
- **Scheduler:** APScheduler (SQLite jobstore)
- **Deployment:** Docker

## Features (MVP)

1. **Dashboard/Sidebar:** List all `.yaml` playbooks in the mounted `/playbooks` directory.
2. **Editor:** Edit playbooks in Ace Editor and save to disk.
3. **Real-Time Terminal:** Run playbooks and stream output live via SSE.
4. **Scheduler:** Simple cron-based scheduling for playbooks.
