# Operational Cheat Sheet

A concise mapping of tasks to the Sible User Interface.

| Objective | Dashboard Location | Action |
| :--- | :--- | :--- |
| **Trigger Playbook** | Dashboard > Playbooks | Click 'Run' on target card |
| **Validate Logic** | Dashboard > Playbooks | Select 'Dry Run' in execution modal |
| **Add Remote Host** | Inventory | Click 'Add Server' |
| **Schedule Backups** | Automation > Cron | Click 'New Schedule' |
| **Rotate Secrets** | Settings > Secrets | Click 'Add Variable' or Edit existing |
| **View Audit Logs** | History | Click log icon on job row |
| **Manage RBAC** | Settings > Users | Edit user and assign Role (Admin/Watcher/Operator) |
| **Set Retention** | Settings > Retention | Configure 'Days to keep' and 'Max logs' |

## Configuration Reference

Sible can be configured using environment variables. These are useful for Docker deployments.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SIBLE_PORT` | `8000` | The port Sible will listen on inside the container. |
| `SIBLE_INFRA_PATH` | `/app/infrastructure` | Internal path where Sible stores playbooks/inventory. |
| `SIBLE_HOST_INFRA_PATH` | `None` | Host machine path for infrastructure (required if using Docker runner). |
| `SIBLE_DATABASE_URL` | `sqlite:////data/sible.db` | Connection string for the SQLite database. |
| `SIBLE_USE_DOCKER` | `True` | Whether to run Ansible inside a separate container (True) or natively (False). |
| `SIBLE_SECRET_KEY` | `sible-...` | Key used for encrypting secrets and session management. **Change this!** |
| `SIBLE_DEBUG` | `False` | Enable debug logging and detailed error messages. |
