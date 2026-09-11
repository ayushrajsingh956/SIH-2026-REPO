# LegalMetro Shield — System Architecture

**Project:** Software System to check compliance of Packaged Commodities under Legal Metrology (Packaged Commodities) Rules, 2011 (Problem Statement ID 26034)  
**Organization:** Ministry of Consumer Affairs, Food & Public Distribution / Department of Consumer Affairs (DoCA)

## Core Architectural Principle
**LLM extracts, code judges.**
The vision model reads images and emits structured field data. Deterministic Python rule validators make every compliance verdict with explainable citations.

## System Topology
- **Web Frontend:** React 18, Vite 5, TypeScript, Tailwind CSS, TanStack Query v5, Zustand.
- **Backend API:** FastAPI modular monolith, SQLAlchemy 2.0 async, asyncpg, Alembic, Pydantic v2.
- **Workers:** Celery 5.x on Redis 7.
- **Storage:** MinIO / S3-compatible object storage.
- **Database:** PostgreSQL 16 with Full-Text Search (TSVector) and `pg_trgm` extension.
