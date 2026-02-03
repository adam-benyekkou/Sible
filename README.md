# Sible
>
> A modern, reactive UI for Ansible Playbooks. Inspired by [Dockge](https://github.com/louislam/dockge).

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Status](https://img.shields.io/badge/status-alpha-orange.svg)

**Sible** is a lightweight, self-hosted Web UI to manage, edit, and run Ansible playbooks. It is designed to be a "no-build" alternative to complex tools like AWX/Tower, focusing on simplicity and a great user experience for homelabbers and DevOps engineers.

---

## 📸 Screenshots

*(Coming Soon)*

---

## ✨ Features

- **Reactive UI**: Built with HTMX and Alpine.js for a snappy, app-like feel without the bloat.
- **File Management**: Edit your `.yaml` playbooks directly in the browser with Ace Editor.
- **Real-Time Logs**: Watch your playbooks run with live terminal output streaming (SSE).
- **Scheduling**: Built-in cron scheduler to automate your tasks.
- **Dark Mode**: Default dark theme inspired by standard IDEs and Dockge.
- **Single Container**: Deploys as a single Docker container. No complex database setup required (uses SQLite).

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTMX, Alpine.js, Pico.css
- **Process Manager**: Ansible Runner / Asyncio
- **Scheduler**: APScheduler

## 🚀 Quick Start

### 1. With Docker Compose (Recommended)

Create a `docker-compose.yml` file:

```yaml
services:
  sible:
    image: sible:latest # (Replace with your build or official image later)
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./playbooks:/playbooks
      - ./data:/app/data # For SQLite database
    environment:
      - SIBLE_SECRET_KEY=change_me
```

Run it:

```bash
docker-compose up -d
```

Visit <http://localhost:8000>

### 2. Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

## 📂 Directory Structure for Playbooks

Mount your existing playbooks folder to `/playbooks`. Sible handles flat directory structures best at the moment.

```text
/playbooks
  ├── deploy-web.yaml
  ├── update-db.yaml
  └── maintenance.yaml
```

## 🤝 Contribution

Contributions are welcome!

1. Fork the Project
2. Create your Feature Branch
3. Commit your Changes
4. Push to the Branch
5. Open a Pull Request

## 📄 License

Destributed under the MIT License.
