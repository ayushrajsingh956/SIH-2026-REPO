# LegalMetro Shield — 100% Free-Tier Production Deployment Guide

This guide details how to deploy the complete **LegalMetro Shield** system into production with **zero ongoing cloud costs ($0/month)** using enterprise free tiers:

| Layer | Recommended Free Provider | Free Tier Limits | S3 / DB Compatibility |
|---|---|---|---|
| **Frontend PWA** | **Vercel** | 100 GB bandwidth / month, automatic SSL, CDN | Native Vite SPA with `vercel.json` |
| **Relational Database** | **Supabase** | 500 MB PostgreSQL 16, pg_trgm extension, pooled | Native PostgreSQL asyncpg compatible |
| **Task Broker & Cache** | **Upstash Redis** | 10,000 commands / day, TLS encryption | Native Redis 7 Celery broker compatible |
| **Object Storage (Media)** | **Cloudflare R2** | 10 GB storage / month, **$0 egress fees** | 100% AWS S3 / MinIO API compatible |
| **Backend API & Workers** | **Render** or **Koyeb** | Free web service + free worker tier | Dockerfile / Python 3.12 native |
| **Multimodal Vision AI** | **Google AI Studio** | 15 Requests / Minute free (Gemini 2.5 Flash) | Official Gemini API Key |

---

## 1. Database Setup: Supabase (PostgreSQL 16)

1. Go to [https://supabase.com](https://supabase.com) and create a free account.
2. Click **"New Project"** (e.g. `legalmetro-db`), choose region (e.g. `ap-south-1` Mumbai / India), and set a secure database password.
3. In Project Settings $\to$ **Database**, copy the connection string under **URI**:
   - For async SQLAlchemy, use:
     ```bash
     DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
     ```
4. Run Alembic migrations from your machine pointing to Supabase:
   ```bash
   DATABASE_URL="postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres" uv run alembic upgrade head
   ```

---

## 2. Broker & Cache: Upstash Redis

1. Go to [https://upstash.com](https://upstash.com) and sign up for free.
2. Click **"Create Database"**, choose region `ap-south-1` (Mumbai), and enable TLS.
3. Copy the **Redis URL** (rediss protocol):
   ```bash
   REDIS_URL=rediss://default:[YOUR-TOKEN]@[YOUR-UPSTASH-ENDPOINT].upstash.io:6379
   ```

---

## 3. Object Storage: Cloudflare R2 (10GB Free, $0 Egress)

1. Go to [https://dash.cloudflare.com](https://dash.cloudflare.com) $\to$ **R2 Object Storage**.
2. Click **"Create Bucket"** $\to$ name it `legalmetro-scans`.
3. In **R2 Manage API Tokens**, click **"Create API Token"** with *Object Read & Write* permissions.
4. Note your credentials:
   ```bash
   MINIO_ENDPOINT=[YOUR-ACCOUNT-ID].r2.cloudflarestorage.com
   MINIO_ACCESS_KEY=[YOUR-R2-ACCESS-KEY-ID]
   MINIO_SECRET_KEY=[YOUR-R2-SECRET-ACCESS-KEY]
   MINIO_BUCKET=legalmetro-scans
   MINIO_SECURE=true
   ```

---

## 4. Vision AI: Google AI Studio

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. Click **"Create API key"** and copy the key:
   ```bash
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash
   OCR_PROVIDER=gemini
   ```

---

## 5. Backend API & Celery Worker: Render (or Koyeb)

1. Go to [https://render.com](https://render.com) and link your GitHub repository.
2. Click **"New +"** $\to$ **Web Service**:
   - **Name**: `legalmetro-api`
   - **Root Directory**: `backend`
   - **Environment**: Docker (uses `backend/Dockerfile`)
   - **Instance Type**: Free
3. Add Environment Variables:
   - `DATABASE_URL`: Your Supabase connection string
   - `REDIS_URL`: Your Upstash Redis URL
   - `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`
   - `GEMINI_API_KEY`: Your Google AI Studio key
   - `JWT_SECRET`: High-entropy 32-character string
   - `ENV`: `production`
   - `CORS_ORIGINS`: `["https://legalmetro.vercel.app"]`
4. Deploy the service. Note the backend URL (e.g. `https://legalmetro-api.onrender.com`).
5. Create a second service for the background worker:
   - **New +** $\to$ **Background Worker** (or use Koyeb free worker).
   - Docker command: `celery -A app.tasks.celery_app worker --loglevel=info -c 2`
   - Same environment variables as API.

---

## 6. Frontend: Vercel

1. Go to [https://vercel.com](https://vercel.com) and click **"Add New Project"**.
2. Select your repository `SIH-2026-REPO`.
3. Configure project settings:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `pnpm run build`
   - **Output Directory**: `dist`
4. Add Environment Variable:
   - `VITE_API_BASE_URL`: `https://legalmetro-api.onrender.com` (your deployed backend URL)
5. Click **"Deploy"**.
6. The `frontend/vercel.json` file automatically handles single-page routing for all officer paths (`/login`, `/dashboard`, `/scans`, `/reports`, `/admin/*`).

---

## 7. Post-Deployment Database Seeder

Once deployed, populate baseline statutory commodities and accounts by triggering the seeder:
```bash
DATABASE_URL="[YOUR-SUPABASE-URL]" uv run python -m app.seed
```
This provisions:
- `admin@legalmetro.gov.in` (`AdminPass123!`)
- `inspector@legalmetro.gov.in` (`InspectorPass123!`)
- `viewer@legalmetro.gov.in` (`ViewerPass123!`)
- 15 standard commodities with barcodes and compliance scans.
