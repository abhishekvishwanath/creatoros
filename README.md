# Creator Intelligence OS

An AI Content + Commercial Intelligence Operating System for growing creators.

The system continuously learns who a creator is, how they communicate, who they serve,
what they've made, what's worked, what the market is doing, and what they should make
next — then helps them execute it and learns from what happens after publication. A
parallel Commercial Intelligence loop uses the same creator brain to find brand
sponsorship fits and run creator-approved outbound.

Content loop: **UNDERSTAND → RESEARCH → DECIDE → CREATE → PUBLISH → MEASURE → LEARN → REPEAT**

Commercial loop: **PROFILE → DISCOVER BRANDS → QUALIFY → SCORE → BRIEF → OUTREACH → RESPOND → DECIDE → LEARN**

See [CLAUDE.md](./CLAUDE.md) for the full product/architecture spec (Part I = content loop,
Part II = commercial loop). This README covers how to run the codebase and what's actually
implemented.

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

The agent service (orchestrator, agents, model router, context builder) lives under
`backend/app/agent_service` — it is not a separate deployable, just another layer inside
the same FastAPI backend, per CLAUDE.md §56 ("avoid unnecessary microservices").

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

Both loops in CLAUDE.md (Part I content loop, Part II commercial loop) are implemented
end-to-end on the backend, with most of it also wired into the frontend. This is further
along than earlier drafts of this README suggested — treat CLAUDE.md §54's build order as
historical sequencing, not a list of what's still outstanding.

### Content Intelligence loop — built

- **Data model + tenant isolation**: full PostgreSQL schema (14 Alembic migrations on top
  of the initial schema) across creator DNA, content, research, strategy, performance,
  experiments/learnings, commercial, and agent observability. Every creator-scoped route
  is gated through `app/api/deps.py::get_owned_creator`. Covered by `backend/tests`
  (unit + integration, one file per service/agent/route group).
- **Agent Service**: real Orchestrator (`agent_service/orchestrator`), Model Router
  (`agent_service/model_router` — Anthropic/Groq/stub, tier-based, never a hard-coded
  model name in agent code), Context Builder (`agent_service/context/builder.py` — bounded,
  task-specific snapshots, never a full DB dump), and strict `AgentOutput` contracts
  (`agent_service/schemas/contracts.py`) enforced at the route layer via `validate_or_502`.
- **Agents implemented**: Creator Intelligence, Audience Intelligence, Opportunity Engine,
  Strategy Engine, Content Architect, Script Agent, Editorial Critic, Performance
  Intelligence — plus the commercial-loop agents below. Each is a real `agent.run()` with
  its own prompt, evidence handling, and proposed-state-change shape, not a placeholder.
- **Full pipelines wired through the API and UI**: onboarding → `/creators/{id}/analyze`
  (Creator DNA: positioning, voice, audience, pillars) → research signal / audience signal
  ingestion → Opportunity Engine (scored, evidence-linked, components shown) → Strategy
  Engine (weekly portfolio) → Content pipeline (brief → script → editorial critique →
  rewrite → schedule/publish, CLAUDE.md §24) → performance ingestion → diagnosis → Learning
  Engine (evidence-gated clustering into `StrategicLearning`, never a single-post rule).
- **Frontend**: Research, Opportunities, Create, Calendar (folds in Strategy), Analytics,
  and Creator DNA pages all call real endpoints and render real state, with honest empty
  states where a creator has no data yet — not fabricated placeholders.

### Commercial Intelligence loop (Part II) — built

- `CommercialProfile` (versioned Commercial DNA), `Brand`/`BrandContact`/`BrandSignal`
  (creator-scoped, manual entry per CLAUDE.md §69), Brand Intelligence Agent (opportunity
  scoring with `contactability` computed in code, never model-guessed, per §71), Campaign
  Intelligence Agent (brief generation), Outreach Agent (initial pitch draft, follow-up
  draft, reply classification/extraction — never a decision, per §66).
- Full loop wired end to end: brand entry → signals → `/opportunities/score` → brand radar
  → campaign brief → outreach thread + drafted pitch → creator approves → creator marks
  sent → creator pastes brand reply → extraction → **creator decision** (the only route
  allowed to write `outcome`/`creator_decision`, enforced in `outreach.py` and the service
  layer) → commercial outcomes feed the *same* `StrategicLearning` table as content
  learnings (`commercial/...` category prefix), so both loops compound into one brain.
- Frontend: `Brands` and `Outreach` pages, Analytics page filters learnings by
  content vs. commercial.

### Known gaps / stale spots

- **Home dashboard** (`apps/web/app/page.tsx`) still renders hard-coded "not connected
  yet" empty states for opportunities/strategy/performance even though those endpoints now
  return real data — it hasn't been rewired since those subsystems landed. Every other
  page was updated; this one was missed.

**Auth**: Supabase Auth is the intended final auth provider, but isn't wired into the
frontend yet. Until then, `POST /creators` finds-or-creates a `User` by email and the
frontend stores the returned `user_id` in `localStorage`, sending it as `X-Debug-User-Id`
on every request (see `backend/app/api/deps.py` and `apps/web/lib/session.ts` — both
clearly marked `TODO(auth)`). Tenant isolation itself is real and tested; only the
identity-proving mechanism is a placeholder.

## What's still missing for a real end-to-end prototype

Everything below is a genuine gap, not a nitpick — see the assistant's summary in-session
for the fuller reasoning on each:

1. Real auth (Supabase Auth wired into the frontend, JWT verification replacing
   `X-Debug-User-Id`).
2. Home dashboard rewired to real opportunity/strategy/performance data (see above).
3. Any platform/API ingestion — content, research signals, audience signals, and
   performance are 100% manual entry today; no YouTube/Instagram/X/Reddit connector exists
   (this is a documented, deliberate MVP choice per CLAUDE.md §69, not an oversight, but a
   prototype a real creator uses daily will hit this wall fast).
4. Semantic memory: the `content_embeddings` pgvector table exists in the schema but
   nothing writes or queries it — no embedding generation, no similarity search. Context
   retrieval today is entirely "most recent N rows," not semantic.
5. Object storage (R2/S3) is not wired — no video/image/media upload or storage path
   exists.
6. Research Agent and Trend Intelligence Agent (CLAUDE.md §11.3–11.4) don't exist as
   agents — research signal ingestion has no normalization, cross-platform aggregation, or
   momentum/saturation analysis behind it, just storage of what's typed in.
7. Repurposing Agent/engine (§11.9, §25) is not built — no source-asset-to-derivatives
   pipeline.
8. Experimentation: `Experiment`/`ExperimentResult` tables exist in the schema but have no
   service, route, or agent — there's no way to create or track a hypothesis-driven test
   today. The Learning Engine only does passive, after-the-fact clustering of performance
   diagnoses.
9. No CI (no `.github/workflows`), no deployment config for Vercel/Railway.
10. `.env.example` model names (`claude-opus-4-1`, `claude-sonnet-4-5`, `claude-haiku-4-5`)
    are out of date relative to the current Claude model family — low-risk since model
    identity is config-only, but worth updating before relying on the Anthropic path.
11. The 5-creator validation protocol (CLAUDE.md §48–49) is a process, not code — no
    baseline-capture tooling or weekly-check tooling exists yet, by design at this stage.
