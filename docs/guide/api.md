# REST API Reference

Sible provides a REST API for programmatic interaction with your infrastructure and automation.

::: info
Most endpoints require authentication via JWT. For programmatic access, you can obtain a token from `/api/auth/login`.
:::

## Core Endpoints

### Health Check
`GET /health`

Returns the system status and version.

**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

## Inventory Management

### List Hosts
`GET /api/inventory/list`

Retrieves a paginated list of all hosts in the inventory.

### Add Host
`POST /api/inventory/add`

Registers a new host in Sible.

**Body (Form Data)**:
* `alias`: String (e.g. `web-01`)
* `hostname`: String (IP or FQDN)
* `ssh_user`: String
* `ssh_port`: Integer (default: 22)
* `ssh_key_secret`: Optional String (Secret name)

## Playbook Orchestration

### List Playbooks
`GET /api/playbooks/list`

Returns a list of available playbooks and their metadata.

### Execute Playbook
`POST /playbook/{name}/run`

Triggers a playbook execution.

**Body (JSON)**:
* `limit`: Optional String (Ansible host limit)
* `tags`: Optional String (Ansible tags)
* `extra_vars`: Optional Object (Dynamic variables)
* `check_mode`: Boolean (Dry run)

## History & Audit

### Job History
`GET /api/history`

Retrieves a paginated list of previous job executions.

### Job Logs
`GET /api/history/{job_id}/logs`

Returns the full execution logs for a specific job.

## User Management

### Current User
`GET /api/users/me`

Returns the profile of the currently authenticated user.
