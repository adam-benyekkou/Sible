# Installation

Sible is primarily distributed as a Docker container, ensuring a consistent environment and simplified deployment lifecycle.

## Prerequisites
- Docker 20.10+
- Docker Compose v2.0+

## Deployment via Docker
```bash
docker run -d \
  -p 8000:8000 \
  -v sible_data:/app/infrastructure \
  ghcr.io/your-org/sible:latest
```
