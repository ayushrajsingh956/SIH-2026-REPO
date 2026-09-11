# LegalMetro Shield — Deployment Guide

## Local Development (Single Command)
```bash
cd infra
docker compose up -d
```

Verify the stack:
```bash
curl http://localhost:8000/healthz
```

Apply database migrations:
```bash
docker compose exec api alembic upgrade head
```
