# REST API Reference

Sible provides a set of endpoints for programmatic interaction. Note that Sible is primarily an HTMX-driven application, so many endpoints accept `application/x-www-form-urlencoded` (Form Data) and return HTML fragments or HTTP 204 No Content with `HX-Trigger` headers.

::: info
Authentication is handled via session cookies. For programmatic access, you must first authenticate against `/api/auth/login` and persist the session cookie.
:::

## Authentication

### Login
`POST /api/auth/login`

**Body (Form Data):**
* `username`: String
* `password`: String

**Response:**
* `200 OK`: Sets `session` cookie.
* `401 Unauthorized`: Invalid credentials.

## Inventory Management

### List Hosts (HTML)
`GET /api/inventory/hosts`

Returns a paginated HTML table of hosts.

**Query Parameters:**
* `page`: Integer (default: 1)
* `search`: String (optional search term)

### Add Host
`POST /api/inventory/hosts`

Registers a new host in the database and syncs to `hosts.ini`.

**Body (Form Data):**
* `alias`: String (Human-readable name)
* `hostname`: String (IP or FQDN)
* `ssh_user`: String (default: root)
* `ssh_port`: Integer (default: 22)
* `ssh_key_secret`: String (Key of the secret in Settings)
* `group_name`: String (Ansible group)

### Update Host
`PUT /api/inventory/hosts/{host_id}`

**Body (Form Data):**
* `alias`: String
* `hostname`: String
* `ssh_user`: String
* `ssh_port`: Integer
* `group_name`: String
* `ssh_key_secret`: String

### Delete Host
`DELETE /api/inventory/hosts/{host_id}`

## Playbook Management

### List Playbooks (HTML)
`GET /api/playbooks/list`

Returns a paginated HTML list of playbooks.

**Query Parameters:**
* `page`: Integer
* `search`: String

### Create Playbook (JSON)
`POST /api/playbooks/create`

Creates a new playbook, optionally from a template.

**Body (JSON):**
```json
{
  "name": "my_new_playbook.yaml",
  "folder": "web/nginx",
  "template_id": "system/update.yaml" 
}
```

### Get Playbook Content
`GET /playbooks/{path}`

Returns the editor UI with the playbook content.

### Save Playbook Content
`POST /playbooks/{path}`

**Body (Form Data):**
* `content`: String (The YAML content)

### Lint Playbook
`POST /lint`

Runs `ansible-lint` on the provided content.

**Body (Form Data):**
* `content`: String (The YAML content)

**Response (JSON):**
Returns a list of linting errors.

## Orchestration

### Run Playbook (UI)
`POST /run/{path}`

Initiates the UI flow for running a playbook (returns the terminal connection fragment).

**Body (Form Data):**
* `limit`: String (Host pattern)
* `tags`: String (Comma-separated tags)
* `verbosity`: Integer (1-4)
* `extra_vars`: String (JSON string or Key=Value)

## Settings & Secrets

### List Secrets (HTML)
`GET /partials/settings/secrets/list`

Returns the HTML list of environment variables.

### Create/Update Secret
`POST /settings/secrets`

**Body (Form Data):**
* `key`: String (e.g., `MY_API_KEY`)
* `value`: String
* `is_secret`: String ("true" to encrypt)

### Delete Secret
`DELETE /settings/secrets/{env_id}`
