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

## 2A. Post-Deploy Smoke Tests (run after every fresh deployment)

These five checks verify the full request path end-to-end. All commands assume the stack is up and `infra` is the working directory.

```bash
BASE=http://localhost   # use http://localhost:8000 when running without the nginx prod profile

# 1. Login as the seeded admin (also confirms migrations + seeder ran)
TOKEN=$(curl -s -X POST $BASE/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@legalmetro.gov.in","password":"AdminPass123!"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
echo "token: ${TOKEN:0:25}..."

# 2. Health + authed read
curl -sf $BASE/healthz | python3 -m json.tool
curl -sf $BASE/api/v1/auth/me -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3. Upload the bundled sample label and poll the scan to completion
#    (exercises: multipart upload -> MinIO -> Celery -> LLM extraction -> rules engine)
SCAN=$(curl -s -X POST $BASE/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -F "images=@../frontend/public/sample_test_label.jpg;type=image/jpeg" \
  -F "mode=retail" -F "font_check_mode=relative")
SID=$(echo "$SCAN" | python3 -c "import json,sys; print(json.load(sys.stdin)['scan_id'])")
until [ "$(docker compose exec -T postgres psql -U postgres -d legalmetro -tAc \
  "SELECT status FROM scans WHERE id='$SID'")" != "processing" ]; do sleep 5; done
docker compose exec postgres psql -U postgres -d legalmetro -tAc \
  "SELECT status, verdict, compliance_score FROM scans WHERE id='$SID'"

# 4. Presigned image renders (the "black image" regression check — must be 200 + image/jpeg)
DETAIL=$(curl -s $BASE/api/v1/scans/$SID -H "Authorization: Bearer $TOKEN")
URL=$(echo "$DETAIL" | python3 -c "import json,sys; print(json.load(sys.stdin)['presigned_image_urls'][0])")
echo "presigned host: $(echo $URL | cut -d/ -f3)"; curl -s -o /dev/null -w "%{http_code} %{content_type}\n" "$URL"

# 5. Extracted fields populated (LLM actually returned data, not an empty schema)
echo "$DETAIL" | python3 -c "
import json,sys
f = json.load(sys.stdin)['extraction']['fields']
print({k: v.get('raw') for k, v in f.items() if v.get('raw')})"
```

**Expected results:** step 1 returns a JWT; step 2 `status: ok` on all deps; step 3 shows
`completed | compliant | ~100.0` for the bundled label; step 4 prints `200 image/jpeg` and the
host portion must be a **client-resolvable** address (see `MINIO_PUBLIC_ENDPOINT` above —
a `minio:9000` host here means the browser will show a black image); step 5 lists populated
fields (`mrp`, `net_quantity`, `mfg_date`, manufacturer name/address, consumer care).

If step 3 stalls in `queued`, check the worker: `docker compose logs worker --tail 50`
(Redis down or broker unreachable are the usual causes; a scan left in `queued` after a
worker restart is recoverable by re-running the same upload).

---

## 2. Environment Configuration Matrix

The following environment variables configure the system across development, staging, and production:

| Variable | Default Value | Required in Prod | Description |
|---|---|---|---|
| `ENV` | `development` | Yes (`production`) | Application environment profile (`production` disables dev mocks). |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/legalmetro` | Yes | Async PostgreSQL connection string. |
| `REDIS_URL` | `redis://localhost:6379/0` | Yes | Redis broker and cache connection string. |
| `MINIO_ENDPOINT` | `localhost:9000` | Yes | S3 / MinIO storage endpoint (without protocol prefix). |
| `MINIO_PUBLIC_ENDPOINT` | `""` (falls back to `MINIO_ENDPOINT`) | Yes (when containers reach MinIO via an internal hostname) | Endpoint **browsers** use to fetch presigned image URLs. Must be resolvable from the client machine (e.g. `http://localhost:9000` in local docker, `https://storage.legalmetro.gov.in` in production). If unset, presigned URLs inherit `MINIO_ENDPOINT` and will render as a black/empty image viewer when the endpoint is a docker-internal hostname. |
| `MINIO_ACCESS_KEY` | `minioadmin` | Yes | MinIO / S3 access key ID. |
| `MINIO_SECRET_KEY` | `minioadmin` | Yes | MinIO / S3 secret access key. |
| `MINIO_BUCKET` | `legalmetro-scans` | Yes | S3 bucket name for evidence photos and reports. |
| `MINIO_SECURE` | `false` | Yes (`true` for HTTPS) | Set `true` if S3 storage utilizes TLS. |
| `JWT_SECRET` | `dev-insecure-secret...` | **CRITICAL** | Minimum 32-character high-entropy secret for HMAC-SHA256 signing. |
| `ACCESS_TOKEN_EXPIRE_MIN` | `30` | No | JWT access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS`| `30` | No | Refresh token validity lifetime in days. |
| `GEMINI_API_KEY` | `""` | Yes | Google Gemini API Key for multimodal extraction. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | No | Vision model identifier. |
| `OCR_PROVIDER` | `gemini` | No | Primary OCR provider (`gemini`, `groq`, or `tesseract`). |
| `GROQ_API_KEY` | `""` | No | Groq API key — used as vision failover when Groq is configured. |
| `GROQ_MODEL` | `groq/compound` | No | Groq model id (must be vision-capable for image input; e.g. `qwen/qwen3.8-27b`). |
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

---

## 6. Admin User Bootstrap

There is no manual "create first user" step — provisioning happens via the idempotent seeder:

```bash
docker compose exec api uv run python -m app.seed
```

What it provisions (all roles verified/created on every run):

| Account | Role | Password |
|---|---|---|
| `admin@legalmetro.gov.in` | admin | `AdminPass123!` |
| `inspector@legalmetro.gov.in` | inspector | `InspectorPass123!` |
| `inspector.mumbai@legalmetro.gov.in` | inspector | `InspectorPass123!` |
| `viewer@legalmetro.gov.in` | viewer | `ViewerPass123!` |

Plus 15 statutory commodities, ~45 seeded scans across verdicts (including a repeat-offender
product), and sample report rows. The seeder is **safe to re-run**: existing users are
verified/reset in place, scans are only generated below a count threshold, and report seeds
only fill gaps.

**Rotating the seeded admin password:** create the replacement via `POST /api/v1/admin/users`
(admin token required) or update the password in the `users` table, then re-run the seeder —
it resets `password_hash` from `USERS_DATA`, so if you rotate secrets in production, update
`USERS_DATA` (or remove the reset block in `backend/app/seed.py`) before re-running.

**Additional admins/inspectors:** create via `POST /api/v1/admin/users` with an admin JWT.
Viewers may self-register at `/register` but land `is_active=false` pending admin approval.
