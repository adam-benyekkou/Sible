# Troubleshooting

This guide addresses common operational friction points and provides resolutions for the Sible orchestration engine.

## 1. SSH Authentication Failure (Permission Denied)
**Cause**: The Sible controller's public key is missing from the target's `authorized_keys`, or the remote user lacks appropriate permissions.
**Resolution**: 
*   Verify the remote user in **Inventory > Edit Host**.
*   Ensure the controller key (found in `Settings > SSH`) is appended to `~/.ssh/authorized_keys` on the target.
*   Test manual connectivity from the Sible container: `docker exec -it sible ssh <user>@<host>`.

## 2. Infrastructure Volume Permission Mismatch
**Cause**: The host directory mounted to `/app/infrastructure` has ownership restricted to `root`, while Sible runs as a non-privileged user.
**Resolution**: Adjust host permissions to match the Sible UID:
`chown -R 1000:1000 /path/to/your/infrastructure`

## 3. Ansible Executable Not Found
**Cause**: The environment PATH does not include `ansible-playbook`, often occurring when running Sible outside of the official Docker image.
**Resolution**: 
*   If using Docker: Ensure you are using the `ghcr.io` image which includes all dependencies.
*   If Native: Verify installation with `ansible --version` and ensure the binary is in the system PATH.

## 4. WebSocket Handshake Failure
**Cause**: A reverse proxy (Nginx/Traefik) is stripping WebSocket headers or blocking the `/ws/` route.
**Resolution**: Ensure your proxy configuration supports 'Upgrade' headers:
```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

## 5. Zombie Job States (Stuck in 'Running')
**Cause**: Sudden container termination or server crash before a job could signal completion.
**Resolution**: Sible automatically cleans up zombie jobs on startup. If a job remains stuck, navigate to **History**, select the job, and use the **Force Terminate** action to reset the state.
