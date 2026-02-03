FROM python:3.11-slim

# Install system dependencies
# - ansible-core needs ssh-client, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ssh-client \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Ansible
RUN pip install --no-cache-dir ansible-core

# Copy Application
COPY . /sible
WORKDIR /sible

# Create a user to run as (optional, but good practice, though for Docker socket access root is often easier in MVP)
# For MVP we stick to root to avoid permission issues with mounted volumes for now.

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
