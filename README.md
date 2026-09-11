# LegalMetro Shield

AI-powered compliance verification system for Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011.

## Structure
- `/backend`: FastAPI service, async SQLAlchemy 2.0, Alembic, Celery workers.
- `/frontend`: Vite 5, React 18, TypeScript, Tailwind CSS, TanStack Query v5.
- `/infra`: Docker Compose setup with PostgreSQL 16, Redis 7, MinIO, API, Worker, and Frontend.
- `/docs`: Architecture, API reference, rules mapping, and deployment guides.
- `/.github/workflows`: Continuous Integration for backend & frontend.

## Quickstart
```bash
cd infra
docker compose up -d
```
Access the application at `http://localhost:5173` and API documentation at `http://localhost:8000/docs`.
