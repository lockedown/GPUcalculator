# GPU Deployment Optimizer

A full-stack web application that dynamically sizes and compares AI infrastructure across NVIDIA Hopper/Blackwell and AMD Instinct GPU roadmaps, visualizing the "sweet spot" across **Performance, Cost, Complexity, and Availability**.

Seeded with real benchmark data from the **Finance GPU Benchmark Matrix** (9 GPUs × 21 benchmarks across 6 finance workload categories).

## Architecture

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router) + TypeScript |
| UI | Tailwind CSS + Lucide icons |
| Charts | D3.js (bubble scatter) + Recharts (radar) |
| State | Zustand |
| Backend | Python FastAPI |
| Database | SQLite (SQLAlchemy ORM) |
| Data Source | `Finance GPU Benchmark Matrix.html` |

## Quick Start

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (macOS/Linux)
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed database (parses HTML benchmark file → SQLite)
python -m app.db.seed

# Start API server
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API docs available at: http://127.0.0.1:8000/api/docs

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open http://localhost:3000

## Pages

- **Dashboard** (`/`) — Summary cards, bubble scatter plot (Cost vs Performance), radar chart, ranked comparison table
- **Hardware** (`/hardware`) — GPU catalog cards with full specs, verdict text, and availability
- **Benchmarks** (`/benchmarks`) — Interactive benchmark matrix (mirrors the HTML source) with workload category and vendor filters
- **Compare** (`/compare`) — Full workload configuration + constraint sliders + all visualizations

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /api/hardware` | GET | List all 9 GPUs with specs |
| `GET /api/hardware/{id}` | GET | Single GPU detail + benchmarks + verdict |
| `GET /api/benchmarks` | GET | All benchmarks, filterable by `?category=` and `?gpu_id=` |
| `GET /api/benchmarks/{category}` | GET | Benchmarks for a workload category |
| `POST /api/compare` | POST | Multi-GPU comparison with sweet-spot ranking |
| `POST /api/calculate` | POST | Run sizing for a workload config |
| `GET /api/networking` | GET | List networking options |

## GPUs Covered

**NVIDIA (6):** H200 SXM5, B100 SXM, B200 SXM, B300 SXM (est.), GB200 NVL72, GB300 NVL72 (est.)

**AMD (3):** MI300X, MI350X (est.), MI355X (est.)

## Benchmark Categories

- **Quantitative Finance** — STAC-A2, Monte Carlo FP64, DGEMM
- **Risk & Compliance** — QuantLib XVA, VaR, Stress Testing
- **AI/LLM Inference** — MLPerf v4, vLLM/TRT-LLM, ONNX RT
- **HPC** — HPL/LINPACK, HPCG, STREAM
- **Trading** — GPU-Direct RDMA, Interconnect BW
- **Tokenization** — Prefill, Decode, Batched Decode, KV Cache, TTFT, Context Length, FP8

## Calculation Engine

- **Performance**: Roofline model (prefill=compute-bound, decode=memory-BW-bound), KV cache sizing, multi-node degradation
- **Cost**: 36-month TCO (CapEx + OpEx), tokens per £ per month
- **Complexity**: Software stack maturity + penalties (cooling, FP8 support, rack-scale)
- **Availability**: Lead time scoring with supply status weighting
- **Composite**: Weighted multi-metric aggregation with configurable weights
