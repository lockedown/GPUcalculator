# GPU Deployment Optimizer

A full-stack web application that dynamically sizes and compares AI infrastructure across NVIDIA Hopper/Blackwell and AMD Instinct GPU roadmaps, visualizing the "sweet spot" across **Performance, Cost, Complexity, and Availability**.

Seeded with real benchmark data from the **Finance GPU Benchmark Matrix** (9 GPUs × 21 benchmarks across 6 finance workload categories).

**Live:** [gpu-calc.vercel.app](https://gpu-calc.vercel.app) · **API:** [gpu-calc-api.vercel.app](https://gpu-calc-api.vercel.app/health)

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Next.js 16     │────▶│  FastAPI (Python) │────▶│ Neon Postgres│
│  Vercel Edge    │     │  Vercel Serverless│     │  (us-east-1) │
│  gpu-calc       │     │  gpu-calc-api     │     │              │
└─────────────────┘     └──────────────────┘     └──────────────┘
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router) + TypeScript |
| UI | shadcn/ui + Tailwind CSS 4 + Lucide icons |
| Charts | D3.js (bubble scatter) + Recharts (radar, line) |
| State | Zustand |
| Backend | Python FastAPI (Vercel serverless) |
| Database | SQLite (local dev) / Neon Postgres (production) |
| ORM | SQLAlchemy 2.0 + NullPool (serverless) |
| Data Source | `Finance GPU Benchmark Matrix.html` |

---

## Quick Start (Local Development)

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
python -m app.db.seed          # Parse HTML → seed SQLite
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/api/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Production Deployment (Vercel + Neon)

### Prerequisites
- Vercel account with GitHub integration
- Neon Postgres project

### 1. Seed Neon Database (one-time, run locally)

```bash
cd backend
pip install psycopg2-binary==2.9.9
DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require" python -m app.db.seed
```

### 2. Create Vercel Projects

**API project** (`gpu-calc-api`):
- Root Directory: `.` (default)
- Framework: Other

**Frontend project** (`gpu-calc`):
- Root Directory: `frontend`
- Framework: Next.js

### Environment Variables

| Project | Variable | Value |
|---------|----------|-------|
| API | `DATABASE_URL` | Neon connection string |
| API | `CORS_ORIGINS` | `https://gpu-calc.vercel.app,http://localhost:3000` |
| Frontend | `NEXT_PUBLIC_API_URL` | `https://gpu-calc-api.vercel.app/api` |

---

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — summary cards, bubble scatter (Cost vs Performance), radar chart, comparison table |
| `/hardware` | GPU catalog — spec cards with cooling, pricing, verdicts |
| `/benchmarks` | Benchmark matrix — interactive heatmap with category/vendor filters |
| `/compare` | Full comparison — workload config + constraint sliders + all visualizations |
| `/gpu/[id]` | GPU deep-dive — specs, benchmarks by category, topology, cost breakdown, rack plan |
| `/prices` | Price tracking — line charts, summary cards, rack-scale toggles |

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check with DB connectivity |
| `/api/hardware` | GET | List all 9 GPUs with specs |
| `/api/hardware/{id}` | GET | GPU detail + benchmarks + availability |
| `/api/benchmarks` | GET | All benchmarks (filter: `?category=`, `?gpu_id=`) |
| `/api/benchmarks/{category}` | GET | Benchmarks for a workload category |
| `/api/compare` | POST | Multi-GPU comparison with sweet-spot ranking |
| `/api/calculate` | POST | Per-GPU sizing results |
| `/api/networking` | GET | Networking options |
| `/api/prices` | GET | Price history for all GPUs |
| `/api/prices/{gpu_id}` | GET | Price history per GPU |
| `/api/export/csv` | POST | CSV export of comparison results |
| `/api/export/json` | POST | JSON export of comparison results |

---

## GPUs Covered

**NVIDIA (5):** H200 SXM5, B200 SXM, B300 SXM *(est.)*, GB200 NVL72, GB300 NVL72 *(est.)*

**AMD (3):** MI300X, MI350X *(est.)*, MI355X *(est.)*

## Benchmark Categories

- **Quantitative Finance** — STAC-A2, Monte Carlo FP64, DGEMM
- **Risk & Compliance** — QuantLib XVA, VaR, Stress Testing
- **AI/LLM Inference** — MLPerf v4, vLLM/TRT-LLM, ONNX RT
- **HPC** — HPL/LINPACK, HPCG, STREAM
- **Trading** — GPU-Direct RDMA, Interconnect BW
- **Tokenization** — Prefill, Decode, Batched Decode, KV Cache, TTFT, Context Length, FP8

## Calculation Engine

- **Performance**: Roofline model (prefill=compute-bound, decode=memory-BW-bound), KV cache sizing, multi-node degradation, calibration against HTML ground-truth
- **Cost**: 36-month TCO (CapEx + OpEx), tokens per £ per month, interconnect-aware network costs
- **Complexity**: Software stack maturity + penalties (cooling, FP8 support, rack-scale)
- **Availability**: Lead time scoring with supply status weighting
- **Rack Planner**: Layout, power budgets, PDU tiers, cooling capacity, density warnings
- **Composite**: Rank-based normalization, benchmark blending, constraint penalties, smart sweet-spot selection

## Tests

```bash
cd backend
python -m pytest tests/ -q    # 180 tests
```
