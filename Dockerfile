# Stage 1: Build Toolchain
FROM python:3.11-slim as builder

# Build-time metadata
LABEL maintainer="cavy.protocol.dev@proton.me"

WORKDIR /build

# Install build-toolchain dependencies (gcc, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Optimize Build Cache: Copy requirements and install before app source
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Slim Runtime Image
FROM python:3.11-slim

# Task 2: GHCR Metadata & OCI Labels
LABEL org.opencontainers.image.source="https://github.com/adam-benyekkou/Sible" \
      org.opencontainers.image.description="Sible - Secure Infrastructure & Building Logic Engine" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="cavy.protocol.dev@proton.me" \
      org.opencontainers.image.title="Sible" \
      org.opencontainers.image.vendor="Cavy Protocol"

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ssh-client \
    sshpass \
    git \
    curl \
    gnupg \
    lsb-release \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root system user for security
RUN groupadd -g 1000 sible && \
    useradd -u 1000 -g sible -m -s /bin/bash sible

WORKDIR /app

# Copy installed python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source code with correct ownership
# This step is last to maximize layer caching for dependency installs
COPY --chown=sible:sible . .

# Ensure necessary directories exist with correct permissions
RUN mkdir -p /app/infrastructure /data/sible && chown -R sible:sible /app/infrastructure /data

# Environment Branding
ENV SIBLE_THEME_LIGHT="Geist Light"
ENV SIBLE_THEME_DARK="Catppuccin Dark"

# Healthcheck for container reliability
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Switch to non-root user
USER sible

# Execute application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
