# LegalMetro Shield — Production Deployment & Operations Guide

This guide details deployment procedures, container orchestration, disaster recovery, environment configuration, and infrastructure hardening for **LegalMetro Shield**.

---

## 1. Quick Start: Production Docker Compose

LegalMetro Shield includes a pre-configured multi-container stack orchestrated via Docker Compose:

### 1.1 Start the Complete Production Stack
```bash
cd infra

# Launch all core services + production Nginx reverse proxy
docker compose --profile prod up -d --build
```

### 1.2 Verify Container Health
```bash
docker compose ps
```
Expected healthy services:
- `legalmetro-postgres` (PostgreSQL 16)
- `legalmetro-redis` (Redis 7)
- `legalmetro-minio` (MinIO Object Storage)
- `legalmetro-minio-setup` (Bucket initializer - exited 0)
- `legalmetro-api` (FastAPI backend)
- `legalmetro-worker` (Celery background worker)
- `legalmetro-frontend` (Vite / PWA static client)
- `legalmetro-nginx` (OWASP-hardened reverse proxy on port 80/443)

### 1.3 Apply Database Migrations & Seed Baseline Data
```bash
# Apply schema migrations
docker compose exec api uv run alembic upgrade head

# Idempotently seed baseline users and commodities
docker compose exec api uv run python -m app.seed
```

### 1.4 Test System Health Probe
```bash
curl -i http://localhost/healthz
```
HTTP 200 Response:
```json
{
  "status": "ok",
  "dependencies": {
    "database": {"status": "ok", "latency_ms": 1.45},
    "redis": {"status": "ok", "latency_ms": 0.82},
    "storage": {"status": "ok", "bucket": "legalmetro-scans", "latency_ms": 3.12}
  }
}
```

---

## 2. Environment Configuration Matrix

The following environment variables configure the system across development, staging, and production:

| Variable | Default Value | Required in Prod | Description |
|---|---|---|---|
| `ENV` | `development` | Yes (`production`) | Application environment profile (`production` disables dev mocks). |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/legalmetro` | Yes | Async PostgreSQL connection string. |
| `REDIS_URL` | `redis://localhost:6379/0` | Yes | Redis broker and cache connection string. |
| `MINIO_ENDPOINT` | `localhost:9000` | Yes | S3 / MinIO storage endpoint (without protocol prefix). |
| `MINIO_ACCESS_KEY` | `minioadmin` | Yes | MinIO / S3 access key ID. |
| `MINIO_SECRET_KEY` | `minioadmin` | Yes | MinIO / S3 secret access key. |
| `MINIO_BUCKET` | `legalmetro-scans` | Yes | S3 bucket name for evidence photos and reports. |
| `MINIO_SECURE` | `false` | Yes (`true` for HTTPS) | Set `true` if S3 storage utilizes TLS. |
| `JWT_SECRET` | `dev-insecure-secret...` | **CRITICAL** | Minimum 32-character high-entropy secret for HMAC-SHA256 signing. |
| `ACCESS_TOKEN_EXPIRE_MIN` | `30` | No | JWT access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS`| `30` | No | Refresh token validity lifetime in days. |
| `GEMINI_API_KEY` | `""` | Yes | Google Gemini API Key for multimodal extraction. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | No | Vision model identifier. |
| `OCR_PROVIDER` | `gemini` | No | Primary OCR provider (`gemini` or `tesseract`). |
| `RATE_LIMITING_ENABLED` | `true` | No | Enables SlowAPI rate limiting (5/min login, 30/min upload). |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Yes | Allowed web origins for CORS policy. |
| `SMTP_HOST` | `""` | Optional | SMTP host for email alerts on failed/needs_review scans. |
| `SMTP_PORT` | `587` | Optional | SMTP port (587 for STARTTLS, 465 for SSL). |
| `SMTP_USER` | `""` | Optional | SMTP username. |
| `SMTP_PASSWORD` | `""` | Optional | SMTP password. |

---

## 3. Production TLS Termination & Ingress

For production environments exposed to the internet, terminate TLS using either **Let's Encrypt / Certbot** with Nginx or a **Caddy** automated proxy.

### Option A: Nginx + Certbot Configuration
Update `infra/nginx.conf` with TLS directives:
```nginx
server {
    listen 80;
    server_name legalmetro.gov.in;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name legalmetro.gov.in;

    ssl_certificate /etc/letsencrypt/live/legalmetro.gov.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/legalmetro.gov.in/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # OWASP Security Headers & Gzip Compression
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(self), microphone=(), geolocation=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' ws: wss:; font-src 'self' data:; frame-ancestors 'none';" always;

    # Proxy rules to backend and frontend...
}
```

### Option B: Automated Caddy Reverse Proxy
```caddyfile
legalmetro.gov.in {
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
    }
    handle /api/* {
        reverse_proxy api:8000
    }
    handle /healthz {
        reverse_proxy api:8000
    }
    handle /ws/* {
        reverse_proxy api:8000
    }
    handle {
        reverse_proxy frontend:5173
    }
}
```

---

## 4. Disaster Recovery: Backup & Restore Runbooks

### 4.1 PostgreSQL Database Backup
Run an automated nightly logical backup using `pg_dump`:
```bash
# Create timestamped dump
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U postgres -Fc legalmetro > "backup_legalmetro_${TIMESTAMP}.dump"

# Encrypt backup
gpg --symmetric --cipher-algo AES256 "backup_legalmetro_${TIMESTAMP}.dump"
```

### 4.2 PostgreSQL Database Restore
To restore database state onto a fresh instance:
```bash
# Terminate existing connections and drop/recreate database
docker compose exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS legalmetro;"
docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE legalmetro;"

# Restore from custom-format dump
docker compose exec -T postgres pg_restore -U postgres -d legalmetro < "backup_legalmetro_${TIMESTAMP}.dump"

# Re-run migrations to ensure consistency
docker compose exec api uv run alembic upgrade head
```

### 4.3 MinIO / S3 Evidence Photos Backup & Mirroring
Backup object storage buckets containing legal evidence photos and generated reports:
```bash
# Mirror MinIO bucket to local directory or secondary S3 bucket
docker run --rm -v $(pwd)/s3_backup:/backup minio/mc:latest \
  mirror myminio/legalmetro-scans /backup/legalmetro-scans
```

---

## 5. Cloud PaaS Deployment (Render / Fly.io / AWS)

### 5.1 Render Deployment
1. **Managed PostgreSQL**: Provision PostgreSQL 16 on Render with connection pooling enabled.
2. **Managed Redis**: Provision Redis 7 instance.
3. **Web Service (API)**:
   - Build Command: `uv sync --no-dev`
   - Start Command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Background Worker**:
   - Start Command: `uv run celery -A app.tasks.celery_app worker --loglevel=info -c 4`
5. **Static Site (Frontend)**:
   - Build Command: `pnpm install && pnpm run build`
   - Publish Directory: `dist`

### 5.2 Fly.io Deployment
Deploy using `fly.toml` with separate process groups:
```toml
app = "legalmetro-shield"
primary_region = "bom" # Mumbai, India region for low latency

[processes]
  app = "uv run uvicorn app.main:app --host 0.0.0.0 --port 8080"
  worker = "uv run celery -A app.tasks.celery_app worker --loglevel=info -c 4"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 2
  processes = ["app"]

[[services.http_checks]]
  interval = "15s"
  timeout = "2s"
  method = "get"
  path = "/healthz"
```
