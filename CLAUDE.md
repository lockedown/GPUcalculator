# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GPU Deployment Optimizer — sizes and compares AI infrastructure across NVIDIA Hopper/Blackwell and AMD Instinct GPUs on Performance, Cost, Complexity, and Availability. Data is seeded from `Finance GPU Benchmark Matrix.html` (9 GPUs × 21 benchmarks across 6 finance workload categories) — that HTML file is the ground-truth data source, not a report artifact; don't delete it.

Monorepo: `backend/` (FastAPI) + `frontend/` (Next.js 16), deployed separately on Vercel (`api/index.py` is the serverless entry point that imports `backend/app/main.py`'s FastAPI app), backed by Neon Postgres in prod / SQLite locally.

## Commands

### Backend (from `backend/`)
```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r ../requirements.txt   # root requirements.txt, not backend/
python -m app.db.seed                # parse HTML -> seed SQLite (gpu_optimizer.db)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
API docs at `http://127.0.0.1:8000/api/docs`.

Tests:
```bash
cd backend
python -m pytest tests/ -q                          # full suite (180 tests)
python -m pytest tests/test_optimizer_v2.py -q       # single file
python -m pytest tests/test_cost.py::test_name -q    # single test
```
`tests/conftest.py` auto-seeds the SQLite test DB once per session (session-scoped autouse fixture) — no manual seed step needed before running tests.

Two standalone root-level scripts (`test_gpu_integration.py`, `simple_test.py`) exercise the engine modules directly without pytest — run with `python test_gpu_integration.py` / `python simple_test.py` from repo root. Useful for quick manual checks of engine logic; not part of the pytest suite.

Seeding against production Neon instead of local SQLite:
```bash
DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require" python -m app.db.seed
```

### Frontend (from `frontend/`)
```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npm run lint
```
Frontend talks to the API via `NEXT_PUBLIC_API_URL` (defaults to `http://127.0.0.1:8000/api` for local dev).

Note: `frontend/AGENTS.md` warns this Next.js version (16) may differ from training-data conventions — check `node_modules/next/dist/docs/` before assuming an API/convention if something looks off.

## Architecture

```
Next.js 16 (frontend/)  --fetch-->  FastAPI (backend/, via api/index.py on Vercel)  -->  Neon Postgres / SQLite
```

- **`api/index.py`** — Vercel serverless entry point. Adds `backend/` to `sys.path` and re-exports `app.main.app`. This is the actual deployed handler for the API project; `backend/app/main.py` is where the real app logic lives.
- **`backend/app/config.py`** — `Settings` reads `DATABASE_URL` and `CORS_ORIGINS` from env; falls back to local SQLite and localhost origins when unset.
- **`backend/app/db/database.py`** — SQLite uses default pooling; Postgres uses `NullPool` (required for serverless — no persistent connections across invocations).
- **`backend/app/db/parse_benchmark_html.py` + `seed.py`** — parse `Finance GPU Benchmark Matrix.html` and populate GPU/Benchmark/Availability/etc. tables. This HTML file is the single source of truth for benchmark numbers; if it changes, re-run the seed.
- **`backend/app/engine/`** — the calculation core, organized by metric axis. Each module is independently testable and has no FastAPI/DB dependency except where noted:
  - `performance.py` — roofline model (prefill = compute-bound, decode = memory-bandwidth-bound), KV cache sizing (GQA-aware), multi-node degradation. Model architecture shapes are keyed by parameter count and matched to nearest known model.
  - `calibration.py` — per-GPU multipliers that correct roofline estimates to match the HTML's real/estimated decode & prefill benchmark numbers (target ±15%). Read this alongside `performance.py` — the roofline output is *not* the final number.
  - `cost.py` — 36/48/60-month TCO (CapEx + OpEx), PUE and $/kWh constants documented inline with their sourcing (Uptime Institute, EIA).
  - `complexity.py` — software stack maturity score + penalties (cooling type, FP8 support, rack-scale), DB-backed (queries `SoftwareStack`).
  - `availability.py` — lead-time scoring with GA/announced/constrained status weighting.
  - `rack_planner.py` — physical rack layout, power budgets, PDU tiers, cooling capacity; imports PUE constants from `cost.py`.
  - `optimizer.py` — aggregates all four axes. Uses rank-based percentile normalization (not min-max, to avoid outlier domination), blends in HTML benchmark scores when a `finance_benchmark_category` is selected, and applies hard-constraint penalties (budget/power/lead-time) rather than just warning. This is the module the `/api/compare` and `/api/calculate` routes call into.
  - Changing any engine constant (PUE, cost/kWh, baseline lead time, etc.) has ranking effects across the optimizer — check `tests/test_optimizer_v2.py` and `test_cost.py` after edits.
- **`backend/app/api/routes/`** — one file per resource (`hardware`, `benchmarks`, `calculate`, `compare`, `networking`, `prices`, `export`), all mounted under `/api` in `main.py`.
- **`backend/alembic/`** — schema migrations; only relevant against Postgres (SQLite path uses `Base.metadata.create_all` directly, see `create_tables()` in `database.py`).

### Frontend
- **`frontend/src/lib/api.ts`** — typed fetch client, one function per API endpoint, shared timeout/error handling.
- **`frontend/src/lib/store.ts`** — Zustand store; the single source of truth for current workload/constraint state, mirrored by `url-state.ts`.
- **`frontend/src/lib/url-state.ts`** — encodes workload+constraints into the query string for shareable links. Only emits values differing from defaults (which must stay in sync with `store.ts` defaults) — this is what backs the "Copy share link" feature and pinned/compared scenarios.
- **`frontend/src/lib/scenarios.ts`** — pinned-scenario persistence (used by the compare page).
- **`frontend/src/components/charts/`** — D3 (bubble scatter) and Recharts (radar, line) visualizations.
- Routing is Next.js App Router under `frontend/src/app/` — one directory per page (`hardware`, `benchmarks`, `compare`, `gpu/[id]`, `prices`, `scenarios`, `methodology`).

## Working across the stack

Schema changes ripple through multiple layers — when adding/changing a field, touch, in order: `backend/app/models/` (SQLAlchemy) → `backend/app/schemas/` (Pydantic) → relevant `engine/` module → `api/routes/` → an Alembic migration if Postgres-affecting → `frontend/src/types/` → `frontend/src/lib/api.ts` → `store.ts`/`url-state.ts` if it's a user-facing workload/constraint field.
