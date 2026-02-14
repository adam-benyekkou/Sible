# Automated Operations

Sible enables proactive infrastructure management through native scheduling and data lifecycle automation.

## Playbook Management
Sible provides a centralized interface for managing Ansible playbooks. Users can view, execute, and monitor playbooks directly from the dashboard.

![Playbooks Overview](/playbooks.png)

Detailed views allow for inspection of playbook content and execution parameters.

![Individual Playbook](/individual_playbook.png)

## Template Library
Sible includes a built-in template system to accelerate playbook development. Templates act as blueprints for common tasks, such as system updates, user provisioning, or stack deployments.

![Template Library](/templates.png)

### Using Templates
1.  Navigate to the Playbooks dashboard and click **New Playbook**.
2.  In the creation modal, select a blueprint from the **Template** dropdown menu.
3.  Provide a name (and optional folder path) for your new playbook.
4.  Click **Create Playbook**.
5.  Sible will instantiate the playbook in your library, populated with the template's content.

## Favorites & Quick Access
Frequently used playbooks can be pinned for rapid access.
1.  Locate the playbook card in the dashboard.
2.  Click the **Heart icon** in the top-right corner.
3.  The playbook will now appear in the **Favorites** section of the sidebar, available from any page in the application.

## Cron-Based Scheduling
A native job scheduler enables the automation of recurring maintenance tasks. SREs can define cron-based intervals for playbooks—such as daily database backups, periodic security patching, or infrastructure health checks—ensuring continuous operational compliance.

![Schedules](/schedules.png)

## Execution Retention Policies
To maintain optimal system performance and prevent database bloat, Sible includes automated data lifecycle management. Retention policies can be configured to prune historical execution logs and job data based on age or volume, ensuring the orchestration hub remains lightweight and responsive.

![Retention Policies](/settings_retention_policies.png)

## Unified Notification Engine
Stay informed of execution outcomes through integrated Apprise support. Sible can send real-time alerts to over 100 services—including Slack, Discord, Telegram, and Microsoft Teams—triggered by job success or failure.

![Notification Settings](/settings_notifications.png)
