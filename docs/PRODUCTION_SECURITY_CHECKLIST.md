# Production Deployment Security Checklist - Sible v1.0.0

This checklist ensures your Sible deployment is hardened for production VPS environments.

---

## 🔴 CRITICAL - Must Complete Before Launch

### 1. Change Default SECRET_KEY

**Current Default:** `sible-secret-key-change-me`

**Action Required:**
```bash
# Generate a secure random key (64+ characters)
openssl rand -hex 64

# Set in environment or .env file
export SIBLE_SECRET_KEY="<generated_key_here>"
```

**Verification:**
```bash
# App will refuse to start in production if using default key
docker-compose up
# Look for: "FATAL: Default SECRET_KEY detected in production"
```

**Risk if not changed:** JWT tokens can be forged, session hijacking possible

---

### 2. Change Default User Passwords

**Default Credentials:**
- `admin` / `admin`
- `operator` / `operator`
- `watcher` / `watcher`

**Action Required:**
1. Login as each user
2. Navigate to Settings → Users
3. Change passwords to strong passphrases (12+ characters)

**Verification:**
- Security warning toast will disappear after password change
- Check: Settings → Users → "Using Default Password" indicator

**Risk if not changed:** Unauthorized access to infrastructure automation

---

### 3. Enable HTTPS

**Current:** HTTP only (session cookies sent in cleartext)

**Action Required:**

**Option A: Reverse Proxy (Recommended)**
```nginx
# /etc/nginx/sites-available/sible.conf
server {
    listen 443 ssl http2;
    server_name sible.example.com;
    
    ssl_certificate /etc/letsencrypt/live/sible.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sible.example.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Option B: Update Docker Compose**
```yaml
# docker-compose.yml
services:
  sible:
    environment:
      - SIBLE_HTTPS_ONLY=true
```

Then edit `app/main.py:195` to enable HTTPS-only cookies:
```python
https_only=True,  # Changed from False
```

**Verification:**
```bash
curl -I https://sible.example.com
# Should see: Strict-Transport-Security header
```

**Risk if not enabled:** Session hijacking, credentials exposed over network

---

## 🟡 IMPORTANT - Recommended for Production

### 4. Use PostgreSQL Instead of SQLite

**Current:** SQLite (single file, no concurrent writes)

**Action Required:**
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb sible_prod
sudo -u postgres createuser sible_user
sudo -u postgres psql -c "ALTER USER sible_user WITH PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sible_prod TO sible_user;"

# Update environment
export SIBLE_DATABASE_URL="postgresql://sible_user:secure_password@localhost/sible_prod"
```

**Benefits:**
- Concurrent access support
- Better performance at scale
- Automatic backups with pg_dump
- Row-level locking

---

### 5. Configure Firewall Rules

**Action Required:**
```bash
# UFW (Ubuntu/Debian)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 80/tcp      # HTTP (for Let's Encrypt)
sudo ufw enable

# For SSH access to managed hosts
sudo ufw allow out 22/tcp
```

**Docker-specific:**
```bash
# Prevent Docker from bypassing UFW
# Edit /etc/ufw/after.rules and add:
*filter
:DOCKER-USER - [0:0]
:ufw-user-forward - [0:0]
-A DOCKER-USER -j ufw-user-forward
-A DOCKER-USER -j RETURN
COMMIT
```

---

### 6. Enable Audit Logging

**Action Required:**

Create `app/middleware/audit.py`:
```python
import logging
from fastapi import Request

audit_logger = logging.getLogger("sible.audit")

async def audit_middleware(request: Request, call_next):
    user = getattr(request.state, 'user', None)
    
    # Log privileged operations
    if request.method in ["POST", "PUT", "DELETE"]:
        audit_logger.info(
            f"USER={user.username if user else 'anonymous'} "
            f"METHOD={request.method} "
            f"PATH={request.url.path} "
            f"IP={request.client.host}"
        )
    
    return await call_next(request)
```

Add to `app/main.py`:
```python
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_middleware)
```

---

### 7. Implement Rate Limiting

**Action Required:**

Install dependency:
```bash
pip install slowapi
```

Add to `app/main.py`:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to login endpoint
@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute
async def login(request: Request, ...):
    ...
```

---

### 8. Rotate SSH Keys Regularly

**Action Required:**
```bash
# Generate new SSH key for Sible
ssh-keygen -t ed25519 -C "sible@production" -f ~/.ssh/sible_prod_ed25519

# Add to Settings → Secrets in Sible UI
# Update all host configurations to use new key

# Remove old key from authorized_keys on managed hosts
```

**Rotation Schedule:** Every 90 days

---

### 9. Enable Database Encryption at Rest

**For PostgreSQL:**
```bash
# Enable pgcrypto extension
sudo -u postgres psql sible_prod -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# Configure PostgreSQL encryption (requires restart)
# Edit /etc/postgresql/14/main/postgresql.conf:
ssl = on
ssl_cert_file = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
ssl_key_file = '/etc/ssl/private/ssl-cert-snakeoil.key'
```

**For SQLite:**
```bash
# Use SQLCipher instead of SQLite
pip install sqlcipher3-binary

# Update DATABASE_URL
export SIBLE_DATABASE_URL="sqlite+pysqlcipher:///:memory:?cipher=aes-256-cfb&kdf_iter=64000"
```

---

### 10. Configure Backup Strategy

**Action Required:**

Create backup script (`/opt/sible/backup.sh`):
```bash
#!/bin/bash
BACKUP_DIR="/opt/sible/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
pg_dump sible_prod | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Backup playbooks
tar -czf "$BACKUP_DIR/playbooks_$DATE.tar.gz" /app/playbooks/

# Backup infrastructure config
tar -czf "$BACKUP_DIR/infrastructure_$DATE.tar.gz" /app/infrastructure/

# Encrypt backups
gpg --encrypt --recipient admin@example.com "$BACKUP_DIR/db_$DATE.sql.gz"

# Upload to S3 or remote storage
aws s3 cp "$BACKUP_DIR/" s3://sible-backups/ --recursive

# Cleanup old backups (keep last 30 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +30 -delete
```

Setup cron job:
```bash
sudo crontab -e
# Add: Daily backup at 2 AM
0 2 * * * /opt/sible/backup.sh
```

---

## 🟢 OPTIONAL - Defense in Depth

### 11. Enable Content Security Policy (CSP)

**Action Required:**

Uncomment in `app/main.py:207`:
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)
```

**Test first:** Verify HTMX and UI still work correctly

---

### 12. Configure Fail2Ban for Brute Force Protection

**Action Required:**
```bash
# Install Fail2Ban
sudo apt install fail2ban

# Create Sible filter
sudo nano /etc/fail2ban/filter.d/sible.conf
```

```ini
[Definition]
failregex = ^.*USER=anonymous METHOD=POST PATH=/api/auth/login IP=<HOST>.*$
ignoreregex =
```

```bash
# Create jail
sudo nano /etc/fail2ban/jail.d/sible.conf
```

```ini
[sible]
enabled = true
port = 80,443
filter = sible
logpath = /var/log/sible/audit.log
maxretry = 5
bantime = 3600
```

```bash
# Restart Fail2Ban
sudo systemctl restart fail2ban
```

---

### 13. Implement SSH Known Hosts Validation

**Current:** SSH host key verification disabled (`known_hosts: None`)

**Action Required:**

Edit `app/routers/ssh.py:87`:
```python
"known_hosts": "/app/.ssh/known_hosts",  # Changed from None
```

Create known_hosts manager:
```bash
# First connection to each host (manual trust)
ssh-keyscan -H managed-host.example.com >> /app/.ssh/known_hosts
```

**Benefit:** Prevents MITM attacks on SSH connections

---

### 14. Set Up Monitoring and Alerting

**Action Required:**

**Option A: Prometheus + Grafana**
```yaml
# docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

**Option B: Sentry for Error Tracking**
```bash
pip install sentry-sdk[fastapi]
```

```python
# app/main.py
import sentry_sdk

sentry_sdk.init(
    dsn="https://your_sentry_dsn@sentry.io/project_id",
    traces_sample_rate=1.0,
)
```

---

### 15. Regular Security Scans

**Action Required:**

Setup automated scans:
```bash
# Weekly cron job
0 3 * * 0 /opt/sible/security-scan.sh
```

`security-scan.sh`:
```bash
#!/bin/bash
# Scan for secrets
gitleaks detect --source /app --verbose --report-path /var/log/gitleaks.json

# Scan dependencies
pip-audit -r /app/requirements.txt > /var/log/pip-audit.log

# Scan Docker image
trivy image sible:latest --severity HIGH,CRITICAL > /var/log/trivy.log

# Email results
mail -s "Weekly Security Scan" admin@example.com < /var/log/trivy.log
```

---

## Verification Checklist

Use this checklist before going live:

```
🔴 CRITICAL
[ ] SECRET_KEY changed from default
[ ] All default user passwords changed
[ ] HTTPS enabled with valid SSL certificate
[ ] Firewall configured and active

🟡 IMPORTANT
[ ] Database: Using PostgreSQL
[ ] Audit logging enabled
[ ] Rate limiting on /login endpoint
[ ] SSH keys rotated (if upgrading)
[ ] Database backups configured
[ ] Backup restoration tested

🟢 OPTIONAL
[ ] Content Security Policy enabled and tested
[ ] Fail2Ban configured
[ ] SSH known_hosts validation enabled
[ ] Monitoring/alerting set up
[ ] Security scanning automated
```

---

## Quick Start Production Deployment

```bash
# 1. Clone repository
git clone https://github.com/your-org/sible.git
cd sible

# 2. Set environment variables
cat > .env <<EOF
SIBLE_SECRET_KEY=$(openssl rand -hex 64)
SIBLE_DATABASE_URL=postgresql://sible:password@db/sible_prod
SIBLE_HTTPS_ONLY=true
SIBLE_DEV_MODE=false
EOF

# 3. Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# 4. Change default passwords
# Login at https://your-domain.com
# Navigate to Settings → Users
# Change all default passwords

# 5. Configure firewall
sudo ufw enable
sudo ufw allow 443/tcp

# 6. Setup backups
sudo crontab -e
# Add: 0 2 * * * /opt/sible/backup.sh
```

---

## Support

- **Security Issues:** security@sible.io
- **Documentation:** https://sible.io/docs
- **Community:** https://github.com/your-org/sible/discussions

---

**Last Updated:** February 12, 2026  
**Version:** v1.0.0
