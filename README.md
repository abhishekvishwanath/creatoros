# Creator Intelligence OS

An AI Content Intelligence & Growth Operating System for growing creators.

The system continuously learns who a creator is, how they communicate, who they serve,
what they've made, what's worked, what the market is doing, and what they should make
next — then helps them execute it and learns from what happens after publication.

Core loop: **UNDERSTAND → RESEARCH → DECIDE → CREATE → PUBLISH → MEASURE → LEARN → REPEAT**

See [CLAUDE.md](./CLAUDE.md) for the full product/architecture spec. This README covers
how to run the codebase.

## Monorepo layout

```
/apps
  /web              Next.js frontend (creator dashboard)
/backend
  /app
    main.py         FastAPI entrypoint
    core/           config, logging
    api/            HTTP routes (domain-oriented, not agent-internal)
    domain/         domain models & business rules per entity
    infrastructure/ db models, session, migrations
    agent_service/  orchestrator, agents, model router, context builder, memory, tools
  /alembic          DB migrations
/tests
  /unit /integration /agent /evaluation
```

## Prerequisites

- Node.js 20+ and pnpm (or npm) for `/apps/web`
- Python 3.11+ and `uv` or `pip` for `/backend`
- A Supabase project (Postgres + pgvector + Auth) — see Setup below
- An Anthropic API key — see Setup below
- Docker (optional, for local Postgres+pgvector before Supabase is wired up)

## Setup

1. **Backend env**: copy `backend/.env.example` to `backend/.env` and fill in:
   - `ANTHROPIC_API_KEY` — from https://console.anthropic.com/settings/keys
   - `DATABASE_URL` — your Supabase Postgres connection string (Project Settings → Database → Connection string, "URI" / Session pooler), or a local Postgres URL for dev
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — from Supabase Project Settings → API

2. **Frontend env**: copy `apps/web/.env.example` to `apps/web/.env.local` and fill in:
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` — where the FastAPI backend runs (default `http://localhost:8000`)

3. **Local Postgres (optional, before Supabase is ready)**:
   ```
   docker compose up -d db
   ```
   This starts Postgres with the `pgvector` extension on port 5432.

4. **Enable pgvector on Supabase**: in the Supabase SQL editor, run `create extension if not exists vector;` once before running migrations against it.

5. **Run migrations**:
   ```
   cd backend
   pip install -r requirements.txt
   alembic upgrade head
   ```

6. **Run the backend**:
   ```
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

7. **Run the frontend**:
   ```
   cd apps/web
   pnpm install
   pnpm dev
   ```

## Status

This is an early-stage scaffold implementing the foundation of the build priority order
in CLAUDE.md §54: data model, creator entity + tenant isolation, agent service skeleton
with structured output contracts, and the dashboard shell IA. Agents currently return
structured stub output when `ANTHROPIC_API_KEY` is not configured, and switch to live
Claude calls once it is set — see `backend/app/agent_service/model_router/router.py`.
