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

# Install Python dependencies as root
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and add to docker group for socket access
RUN groupadd -r sible && useradd -r -m -g sible -u 1000 sible \
    && groupadd -g 999 docker_host && usermod -aG docker_host sible

# Setup application directory
WORKDIR /sible
COPY --chown=sible:sible . .

# Ensure permissions for playbooks and inventory
RUN mkdir -p /sible/playbooks /sible/inventory /sible/.jobs \
    && chown -R sible:sible /sible

# Expose port
EXPOSE 8000

# Switch to non-root user
USER sible

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
