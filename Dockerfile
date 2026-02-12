# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies if needed (e.g., for some python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Install system dependencies
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

# Create a non-root system user named sible
RUN groupadd -g 1000 sible && \
    useradd -u 1000 -g sible -m -s /bin/bash sible

# Set work directory
WORKDIR /app

# Copy installed python packages from builder
COPY --from=builder /install /usr/local

# Copy application code with correct ownership
COPY --chown=sible:sible . .

# Setup infrastructure and data directories
RUN mkdir -p /app/infrastructure /data && chown -R sible:sible /app/infrastructure /data

# Environment Branding
ENV SIBLE_THEME_LIGHT="Geist Light"
ENV SIBLE_THEME_DARK="Catppuccin Dark"

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Switch to non-root user
USER sible

# Run the application
# We use a shell to ensure we can handle volume permissions if needed on entry
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
