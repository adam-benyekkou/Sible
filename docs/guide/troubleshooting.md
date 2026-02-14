# Troubleshooting

This guide addresses common operational friction points and provides resolutions for the Sible orchestration engine.

## 1. Permission Denied (Database / Data)
**Symptoms**: Container fails to start or shows `sqlite3.OperationalError: unable to open database file`.
**Cause**: The Sible container user (UID 1000) does not have write access to the mounted `./data` volume.
**Resolution**: 
```bash
sudo chown -R 1000:1000 ./data
```

## 2. Playbooks Not Visible in Dashboard
**Symptoms**: Dashboard shows "No automation found" even though files exist on the host.
**Cause**: Sible cannot read the playbooks directory due to permission restrictions.
**Resolution**: Ensure the files are readable by UID 1000:
```bash
sudo chown -R 1000:1000 /path/to/your/ansible/files
```

## 3. Terminal Error: "Invalid Private Key"
**Symptoms**: SSH terminal fails immediately with "Error importing Private Key Secret".
**Cause**: The SSH key in **Settings > Environments** has incorrect formatting (missing newlines or accidental trailing spaces).
**Resolution**: 
*   Ensure the key starts with `-----BEGIN...` and ends with `-----END...`.
*   Re-paste the key into the secret field and save. Sible automatically cleans up most formatting issues, but a clean paste is recommended.

## 4. Docker API Permission Denied
**Symptoms**: Running a playbook fails with `permission denied while trying to connect to the docker API`.
**Cause**: The Sible container is trying to launch another container for Ansible but doesn't have access to the host's Docker socket.
**Resolution**:
*   **Recommended**: Disable the Docker runner by setting `SIBLE_USE_DOCKER=False` in your environment variables. This will run Ansible natively inside the Sible container.
*   **Alternative**: Grant access to the socket (less secure): `sudo chmod 666 /var/run/docker.sock`.

## 5. Connection Error: ('127.0.0.1', 22)
**Symptoms**: Cannot connect to `local_server`.
**Cause**: `127.0.0.1` inside a container refers to the container itself, not the host machine.
**Resolution**: Change the server Hostname/IP to your VPS Public IP or the Docker gateway IP (usually `172.17.0.1`).

## 6. WebSocket Handshake Failure
**Symptoms**: Real-time logs or Terminal don't load.
**Cause**: A reverse proxy (Nginx/Traefik) is stripping WebSocket headers.
**Resolution**: Ensure your proxy configuration supports 'Upgrade' headers:
```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

## 7. Ansible Galaxy Errors
**Symptoms**: A playbook fails with `ERROR! the role 'xyz' was not found`.
**Cause**: The playbook relies on external roles or collections that are not installed in the container.
**Resolution**:
*   Ensure a `requirements.yml` file exists in the same directory as your playbook (or parent directory).
*   In the Sible UI, open the playbook and look for the **Install Requirements** button (visible if `requirements.yml` is detected).
*   Click it to run `ansible-galaxy install` automatically.

## 8. Linting Warnings
**Symptoms**: You see yellow/red warning indicators in the playbook editor.
**Cause**: Sible runs `ansible-lint` on save. These are best-practice suggestions (e.g., "Use shell only when necessary", "Task should have a name").
**Resolution**:
*   Review the suggestions to improve your playbook's reliability.
*   You can ignore them if strict adherence isn't required; they do not prevent execution.
