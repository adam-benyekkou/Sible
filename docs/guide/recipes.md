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
**Sible Implementation**: Use <code>{{ "lookup('env', 'GHCR_TOKEN')" }}</code> in your playbook, and define `GHCR_TOKEN` in **Settings > Secrets**.
