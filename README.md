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
    core/           config, logging, id generation
    api/            HTTP routes (domain-oriented, not agent-internal)
    domain/         SQLAlchemy models & business rules, one package per entity group
    infrastructure/ db session, Base, cross-module model registry
  /alembic          DB migrations
  /tests
    /unit /integration
```

The agent service (orchestrator, agents, model router, context builder, memory, tools)
lives under `backend/app/agent_service` once it's built (see Status below) — it is not a
separate deployable, just another layer inside the same FastAPI backend, per CLAUDE.md §56
("avoid unnecessary microservices").

## Prerequisites

- Node.js 20+ and npm for `/apps/web`
- Python 3.11+ for `/backend`
- A Supabase project (Postgres + pgvector + Auth) — see Setup below
- An Anthropic API key — see Setup below
- Docker (optional, for local Postgres+pgvector before Supabase is wired up)

## Setup

1. **Backend env**: copy `backend/.env.example` to `backend/.env` and fill in:
   - `ANTHROPIC_API_KEY` — from https://console.anthropic.com/settings/keys
   - `DATABASE_URL` — your Supabase Postgres connection string (Project Settings → Database
     → Connection string, "URI" / Session pooler — **not** the transaction pooler on port
     6543, asyncpg needs session mode), or a local Postgres URL for dev
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` — from Supabase
     Project Settings → API
   - `WEB_ORIGIN` — the URL the frontend runs on (default `http://localhost:3000`; if that
     port is taken locally and you run Next on another port, update this to match or CORS
     will reject requests)

2. **Frontend env**: copy `apps/web/.env.example` to `apps/web/.env.local` and fill in:
   - `NEXT_PUBLIC_API_URL` — where the FastAPI backend runs (default `http://localhost:8000`)
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — leave blank for now; see
     Status below on the dev-mode auth stand-in

3. **Local Postgres (optional, before Supabase is ready)**:
   ```
   docker compose up -d db
   docker exec <db-container> psql -U creatoros -d creatoros -c "create extension if not exists vector;"
   ```
   This starts Postgres with the `pgvector` extension on port 5544 (chosen to avoid
   clashing with a system Postgres on the default 5432 — change the port mapping in
   `docker-compose.yml` and `DATABASE_URL` together if you'd rather use 5432).

4. **Enable pgvector on Supabase**: in the Supabase SQL editor, run
   `create extension if not exists vector;` once before running migrations against it.

5. **Run migrations**:
   ```
   cd backend
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/alembic upgrade head
   ```

6. **Run the backend**:
   ```
   cd backend
   .venv/bin/uvicorn app.main:app --reload --port 8000
   ```

7. **Run the frontend**:
   ```
   cd apps/web
   npm install
   npm run dev
   ```

8. **Run backend tests** (spins up against a `creatoros_test` database on the same
   Postgres instance — create it once with `create database creatoros_test;` +
   `create extension if not exists vector;`):
   ```
   cd backend
   .venv/bin/pytest
   ```

## Status

Implemented so far, in the order laid out in CLAUDE.md §54:

- **Data model + Creator entity + tenant isolation**: the full PostgreSQL schema (34
  tables across creator DNA, content, research, strategy, performance, experiments, and
  agent observability), with every creator-scoped route gated through
  `app/api/deps.py::get_owned_creator` so one user can never read or mutate another's
  data. Covered by an automated test suite (`backend/tests`).
- **Dashboard shell + IA**: the Next.js frontend implements the information architecture
  from CLAUDE.md §38 (Home, Research, Opportunities, Create, Calendar, Analytics, Creator
  DNA) with an onboarding flow, real data binding to whatever backend state actually
  exists, and honest empty states (never fabricated data) for subsystems not built yet.

Not yet built: the agent service (orchestrator, model router, context builder, and the
actual agents), content ingestion, research/opportunity/strategy engines, and performance
ingestion. Home and Creator DNA will visibly fill in as each of those lands.

**Auth**: Supabase Auth is the intended final auth provider, but isn't wired into the
frontend yet. Until then, `POST /creators` finds-or-creates a `User` by email and the
frontend stores the returned `user_id` in `localStorage`, sending it as `X-Debug-User-Id`
on every request (see `backend/app/api/deps.py` and `apps/web/lib/session.ts` — both
clearly marked `TODO(auth)`). Tenant isolation itself is real and tested; only the
identity-proving mechanism is a placeholder.
