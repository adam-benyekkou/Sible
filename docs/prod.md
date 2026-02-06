# Product Definition (MVP)

## The Problem

Running Ansible playbooks often requires using the command line. Existing UI tools (like AWX/Tower) are often too heavy, complex to set up, and resource-intensive for homelabbers or small DevOps teams who just want a clean UI to run and edit scripts.

## The Solution

**Sible**: A "no-build", single-container Docker application that gives a polished UI for Ansible. It connects directly to a folder of YAML files, allowing users to edit them in a browser and run them with visual feedback.

## MVP Scope (Minimum Viable Product)

The initial release will focus on the core "Write -> Run -> Watch" loop.

### In Scope

- **File Management:** Reading/Writing `.yaml` files from a local directory.
- **Execution:** Triggering `ansible-playbook` commands.
- **Live Logs:** Streaming stdout/stderr to the browser in real-time.
- **Basic UI:** Two-pane layout (Sidebar list, Main editor/terminal).
- **Scheduling:** Basic cron job setup.

### Out of Scope (for now)

- Database-backed user management (Single user/Basic Auth for MVP).
- Complex inventory management UI (User relies on `hosts.ini` or inline inventory).
- Secrets management within the UI (Relies on environment vars or Ansible Vault).
- Git integration (Users sync files via volume mounts).
