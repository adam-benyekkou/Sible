# Architecture

Sible follows a modern, decoupled architecture designed for high throughput and security.

## Tech Stack
- **Backend**: FastAPI (Python)
- **Database**: SQLModel (ORM)
- **Frontend**: HTMX / PicoCSS
- **Orchestration**: Ansible Subprocesses
- **Communication**: WebSockets (Real-time logs)

## Component Overview

```mermaid
flowchart TB
    subgraph Client [Browser]
        UI[HTMX / Alpine.js]
        WS_Client[WebSocket Client]
    end

    subgraph Server [Sible Container]
        API[FastAPI Router]
        Auth[Auth Middleware]
        
        subgraph Services
            Runner[Ansible Runner Service]
            Scheduler[Cron Scheduler]
            Inventory[Inventory Service]
        end
        
        DB[(SQLite Database)]
        Vault[Secret Vault]
    end

    subgraph Execution [Ansible Core]
        Process[Subprocess / Docker]
        SSH[OpenSSH Client]
    end

    subgraph Targets [Infrastructure]
        VPS[Remote Server]
        Cloud[Cloud Instance]
    end

    %% Flows
    UI -->|HTTP/HTMX| Auth
    Auth --> API
    API --> Services
    
    Runner -->|Spawn| Process
    Process -->|SSH| SSH
    SSH -->|Execute| Targets
    
    Services -->|Read/Write| DB
    Services -->|Decrypt| Vault
    
    Process -.->|Stream Logs| WS_Client
    WS_Client -.->|Terminal Input| Process
```

## Data Flow
1.  **Request**: User triggers a playbook via the HTMX UI.
2.  **Validation**: Request is authenticated and RBAC checks are performed.
3.  **Execution**: The Runner Service spawns an isolated Ansible subprocess (or Docker container).
4.  **Streaming**: stdout/stderr are captured in real-time and pushed to the browser via WebSockets.
5.  **Persistence**: Job status and audit logs are written to SQLite.

