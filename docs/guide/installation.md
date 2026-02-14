# Installation

Sible is primarily distributed as a Docker container, ensuring a consistent environment and simplified deployment lifecycle.

## Prerequisites
- Docker 20.10+
- Docker Compose v2.0+

## Recommended: Docker Compose
Using Docker Compose is the most reliable way to manage Sible's persistence and Ansible file integration.

Create a `docker-compose.yml` file:

```yaml
services:
  sible:
    image: ghcr.io/adam-benyekkou/sible:v1.0.0
    container_name: sible
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      # Map your Ansible project to the container
      - /opt/infrastructure/ansible:/opt/infrastructure/ansible
      # Persistent data for database and logs
      - ./data:/data
      # Optional: Docker socket if using Docker-in-Docker for Ansible runners
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - SIBLE_PORT=8000
      # Path inside the container to your Ansible files
      - SIBLE_INFRA_PATH=/opt/infrastructure/ansible
      # Path on the HOST to your Ansible files (required if SIBLE_USE_DOCKER=True)
      - SIBLE_HOST_INFRA_PATH=/opt/infrastructure/ansible
      # Set to False to run Ansible natively inside the Sible container (Recommended for simplicity)
      - SIBLE_USE_DOCKER=False
      # Change this to a secure random string
      - SIBLE_SECRET_KEY=sible-production-key-change-me
```

### Initial Setup
Before starting the container, ensure your local directories have the correct permissions for the Sible user (UID 1000):

```bash
mkdir -p data
sudo chown -R 1000:1000 data
sudo chown -R 1000:1000 /opt/infrastructure/ansible
```

Then launch the application:
```bash
docker compose up -d
```

## Manual Run (Docker CLI)
```bash
docker run -d \
  -p 8000:8000 \
  -v /opt/infrastructure/ansible:/opt/infrastructure/ansible \
  -e SIBLE_INFRA_PATH=/opt/infrastructure/ansible \
  -e SIBLE_USE_DOCKER=False \
  ghcr.io/adam-benyekkou/sible:v1.0.0
```
