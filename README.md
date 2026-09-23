# MDM Web App

Multi-tenant SaaS rewrite of the Noor MDM Cleansing & Migration tool (originally
a single-user Streamlit app) as a scalable web application: a FastAPI backend,
a Next.js frontend, Postgres with one schema per tenant, background job
workers, and an agentic "talk to your data" layer built on the Claude API.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and
[`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased build plan.

## Project layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, Arq workers
frontend/   Next.js (TypeScript) app, Clerk auth
docs/       Architecture and roadmap notes
```

## Local development

Prerequisites: Docker + Docker Compose.

1. Copy the environment templates and fill in real values:
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env.local
   ```
2. Start everything:
   ```bash
   docker compose up --build
   ```
   This brings up Postgres, Redis, the FastAPI backend (`:8000`), the Arq
   worker, and the Next.js frontend (`:3000`).
3. Run database migrations (first time, and after any model change):
   ```bash
   docker compose exec backend alembic upgrade head
   ```

## Status

Phase 1 (foundations + first vertical slice: Load Data → Address Cleansing +
chat-with-data agent) is in progress. See `docs/ROADMAP.md`.
