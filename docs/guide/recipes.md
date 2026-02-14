# Recipe Gallery

Standardized playbook patterns for rapid infrastructure management.

## 1. Fleet-Wide Security Patching
**Objective**: Update all packages and reboot if necessary.
```yaml
- name: Security Patching
  hosts: all
  become: yes
  tasks:
    - name: Update apt cache and upgrade packages
      apt:
        upgrade: dist
        update_cache: yes
    - name: Check if reboot is required
      stat:
        path: /var/run/reboot-required
      register: reboot_required
    - name: Reboot server
      reboot:
        msg: "Sible: Security patch reboot"
      when: reboot_required.stat.exists
```

## 2. Infrastructure Observability
**Objective**: Rapid audit of disk utilization and CPU load across the fleet.
```yaml
- name: Disk Usage Audit
  hosts: all
  tasks:
    - name: Fetch disk usage
      command: df -h /
      register: disk_out
    - name: Display status
      debug:
        msg: "Host {{ 'inventory_hostname' }} Disk: {{ 'disk_out.stdout_lines[1]' }}"
```

## 3. Ephemeral Registry Authentication
**Objective**: Inject a GHCR token for short-lived pull operations without persisting credentials.
**Sible Implementation**: Use `{{ "lookup('env', 'GHCR_TOKEN')" }}` in your playbook, and define `GHCR_TOKEN` in **Settings > Secrets**.

## 4. Docker Container Lifecycle
**Objective**: Deploy or update a Docker container with specific environment variables.
```yaml
- name: Deploy Sible
  hosts: all
  tasks:
    - name: Ensure sible container is running
      docker_container:
        name: sible
        image: ghcr.io/adam-benyekkou/sible:v1.0.0
        state: started
        restart_policy: always
        published_ports:
          - "8000:8000"
        env:
          SIBLE_SECRET_KEY: "{{ secret_key }}"
          SIBLE_USE_DOCKER: "False"
```

## 5. System Health Reporting
**Objective**: Generate a summary of system status for notifications.
```yaml
- name: System Report
  hosts: all
  tasks:
    - name: Gather system stats
      shell: |
        echo "CPU: $(top -bn1 | grep Load | awk '{print $3}')"
        echo "Memory: $(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')"
      register: stats_out

    - name: Notify Sible
      debug:
        msg: "System Stats for {{ inventory_hostname }}: {{ stats_out.stdout }}"
```

## 6. Dynamic User Configuration
**Objective**: Provision a new user account across the fleet.
```yaml
- name: Provision Developer User
  hosts: all
  become: yes
  vars_prompt:
    - name: developer_username
      prompt: "Enter the username for the new developer"
      private: no
  tasks:
    - name: Create user account
      user:
        name: "{{ developer_username }}"
        shell: /bin/bash
        groups: sudo
        append: yes
```
