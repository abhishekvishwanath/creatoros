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
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — from Supabase Project
     Settings → API. Leave both blank to run in dev-mode auth instead (a local placeholder
     identity, no Supabase project needed at all) — see Status below. Setting these also
     requires setting `SUPABASE_URL` in `backend/.env` (step 1) for the backend to verify
     the resulting sessions; without both halves set together, requests will fail auth.

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
- **Agents implemented**: Creator Intelligence, Audience Intelligence, Trend Intelligence,
  Opportunity Engine, Strategy Engine, Content Architect, Script Agent, Editorial Critic,
  Repurposing Agent, Performance Intelligence, Experimentation Agent — plus the
  commercial-loop agents below. Each is a real `agent.run()` with its own prompt, evidence
  handling, and proposed-state-change shape, not a placeholder.
- **Full pipelines wired through the API and UI**: onboarding → `/creators/{id}/analyze`
  (Creator DNA: positioning, voice, audience, pillars) → research signal / audience signal
  ingestion → Trend Intelligence (momentum computed in code, saturation/durability/
  relevance judged by the model) → Opportunity Engine (scored, evidence-linked, components
  shown) → Strategy Engine (weekly portfolio) → Content pipeline (brief → script →
  editorial critique → rewrite → schedule/publish → Repurposing Agent for platform-native
  derivatives, CLAUDE.md §24/§25) → performance ingestion → diagnosis → Learning Engine
  (evidence-gated clustering into `StrategicLearning`) → Experimentation (hypothesis →
  test/control results → evaluated verdict, promoted into that same learning table).
- **Auth**: real Supabase Auth (email/password), wired end to end — `apps/web/app/login`,
  JWT verification in `backend/app/api/deps.py::get_current_user_id` against the project's
  public JWKS (falls back to a legacy HS256 `SUPABASE_JWT_SECRET` for older projects that
  haven't moved to asymmetric signing keys), user auto-provisioning on first authenticated
  request. Gracefully degrades to the original `X-Debug-User-Id` dev/test path whenever
  `SUPABASE_URL` isn't configured, so local dev and the test suite need zero Supabase setup
  — same precedent as `ModelRouter` falling back to stub mode with no API key.
- **Frontend**: Research, Opportunities, Create, Calendar (folds in Strategy), Analytics,
  Experiments, Home, and Creator DNA pages all call real endpoints and render real state,
  with honest empty states where a creator has no data yet — not fabricated placeholders.

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

### Platform ingestion + semantic memory — built

- **YouTube link ingestion** (`app/domain/ingestion`): a creator pastes their channel URL
  (onboarding, or any time from the Creator DNA page) and the backend resolves it to a
  channel via YouTube's public channel page, pulls recent uploads from its public RSS feed,
  and best-effort fetches each video's public caption track for transcript text — all
  unauthenticated, no API key or OAuth app required (CLAUDE.md §17.1's "compliant fallback
  mechanism" in practice). Each video becomes a `ContentItem`; re-importing the same channel
  upserts by video id instead of duplicating. Instagram/X/Reddit connectors remain a real
  gap (#1 below) — YouTube was the one platform with a reliable unauthenticated path.
- **Semantic memory** (`app/agent_service/memory`, `app/domain/memory`): `content_embeddings`
  is now live — a local ONNX embedding model (`BAAI/bge-small-en-v1.5` via `fastembed`, no
  API key, no network call at embed time) runs on every script, ingested transcript,
  audience signal, research signal, and strategic learning as it's written. The Script
  Agent's context now includes the creator's own semantically-closest past
  scripts/transcripts (CLAUDE.md §10's own example) instead of only recency-bounded lists,
  and `GET /creators/{id}/memory/search` (surfaced in the UI as "Search your memory" on the
  Creator DNA page) lets a creator query across everything embedded so far by meaning, not
  keyword.

## What's still missing for a real end-to-end prototype

Everything below is a genuine gap, not a nitpick:

1. Instagram/X/Reddit ingestion, and research-signal/audience-signal/performance ingestion
   generally, are still 100% manual entry — only YouTube has a connector (see above). A
   prototype a real creator uses daily will still hit this wall for every platform but one.
2. Object storage (R2/S3) is not wired — no video/image/media upload or storage path
   exists.
3. Research Agent (CLAUDE.md §11.3) doesn't exist as a live cross-platform fetcher — Trend
   Intelligence now reasons over signals once they're in the system (momentum/saturation/
   durability/relevance), but nothing goes and finds those signals itself; that's still
   gated on #1 above.
4. No CI-enforced deployment (`.github/workflows` runs tests + build on every push, but
   there's no Vercel/Railway deploy config yet).
5. The 5-creator validation protocol (CLAUDE.md §48–49) is a process, not code — no
   baseline-capture tooling or weekly-check tooling exists yet, by design at this stage.

Shipped since the last pass over this list (all with passing unit/integration tests and a
live smoke test against a real Supabase project, not just mocked): Home dashboard rewire,
Repurposing Agent, Experimentation engine, Trend Intelligence Agent, CI, real Supabase Auth,
YouTube link ingestion, and semantic memory (local embeddings + search).
