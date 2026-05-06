# Roadmap

Tracks where the GPU Deployment Optimizer is going.

**Current shipping version: v2.2.** The API-review backlog (TTFT/TPOT, MoE
routing, NVLink topology, MIG / Run:ai multi-tenancy, disaggregated
prefill/decode) landed in v2.0, then got a code-quality cleanup pass in
v2.1, then customer-fit polish (sweet-spot explainer, workload templates,
carbon cost, regional pricing, optimizer perf SLO) in v2.2.

## v2.2 — sweet-spot fluency + customer fit (✅ shipped)

Targets the gap between *"what does this dashboard tell me"* and *"what does
my customer want to discuss in a 30-minute call?"*. Ordered roughly by ratio
of customer payoff to engineering effort.

| # | Item | Why now | Effort |
|---|------|---------|--------|
| 1 | **Sweet-spot explainer** — surface *why* a GPU was recommended (best $/tok, lowest TTFT, only one passing all hard constraints, etc.). The composite score alone is opaque in meetings. | Cheap. Data already exists; just render the deciding axis next to the badge. | S |
| 2 | **Workload templates** — "Chat at scale", "RAG enterprise", "Training run", "Quant Monte Carlo" preset buttons that fill the form in one click. | Cuts time-to-first-comparison from minutes to seconds. Big demo win. | S |
| 3 | **Carbon cost surfacing** — kg CO₂ / year from `tdp × hours × grid_intensity`. One new column on the comparison table; inputs already in the model. | TCO conversations increasingly include sustainability. | S |
| 4 | **Optimizer perf SLO** — assert `run_comparison` stays <100 ms on the 10-GPU catalogue. Currently <1 ms; lock that in before the next sprint eats the headroom. | Cheap; protects the dev loop and live API responsiveness. | S |
| 5 | **Sprint-10 v2: heterogeneous SKU disaggregation** — let the user pick GPU A for the prefill pool and GPU B for the decode pool; size + cost both pools independently. | Closes the "real customer ask" hinted at in the original API review. The deferred follow-up. | L |
| 6 | **Power-cost regional override** — replace the single `colo_usd_per_kw_per_month` input with a region picker (US-East / US-West / EU / APAC) that swaps in CBRE-derived defaults. | Today's number is US-only; non-US customers get wrong TCO out of the box. | S |

## v2.3 — data quality + freshness

Lower customer visibility but matters for the engine's credibility over time.

| # | Item | Why | Effort |
|---|------|-----|--------|
| 7 | **Single-source GPU data** — collapse `neon_update.sql` and `seed.py` GPU_EXTRA_DATA into one canonical YAML/JSON the build reads from. | Prevents the schema-vs-prod-DB desync we hit during the v2.0 deploy. | M |
| 8 | **Calibration freshness stamp** — `REFERENCE_DECODE` / `REFERENCE_PREFILL` are anchored to specific benchmark snapshots. Surface a "calibration version" + a smoke test that flags drift against a fresh snapshot. | The reference numbers will go stale; protect against silent drift. | M |
| 9 | **Scheduled benchmark refresh** — cron that pulls latest MLPerf / vLLM / NVIDIA published results into the calibration table. | Tied to #8; blocked until that lands. | M |
| 10 | **Reliability / spares model** — account for fault-tolerant capacity (e.g. +N% over baseline `gpu_count` for HA). | Real production deployments don't size to baseline; current numbers are slightly optimistic. | M |
| 11 | **Price freshness + auto-refresh** — same pattern as #8 but for the pricing data. Adds an `msrp_as_of` date column to `gpus`, surfaces "Prices as of YYYY-MM-DD" on the comparison table + per-GPU detail page, and ships a refresh mechanism (small admin endpoint + scheduled cron) that pulls from known-good sources — NVIDIA / AMD official MSRPs, channel surveys (UBS, SemiAnalysis), CBRE colo rates, EPA eGRID grid intensity — and writes new `price_history` entries automatically. Today's MSRPs are static and unstamped: a customer reading "$30k" doesn't know whether that reflects 2024 launch, 2026 channel reality, or hand-wave estimate. | Pricing in this sector is moving 10-30% per year; without stamps + auto-refresh the dashboard's most-asked numbers will silently drift. Pairs with #7 (data must be in the canonical YAML so refresh has a structured target to write back to) and #8 (same staleness pattern, different data). | M |

## Deferred / parking lot

Not on the v2.x track but listed so we don't re-discover them.

- **Authentication + saved scenarios** — would need backend persistence; URL-only sharing covers most current use cases.
- **Multi-tenancy v2 — heterogeneous tenants** — different workloads sharing the same GPU. Builds on Sprint 11 single-tenant sizing. Useful but specialist.
- **Dashboard sub-components** — `WorkloadForm.tsx` / `SweetSpotDetail.tsx` are getting long but inline rows still read fine. Revisit if a 5th conditional row lands.
- **CODE_LABELS shared mapping** — currently lives in `SweetSpotDetail.tsx` only. Move to a shared module if a second consumer needs it.
- **`TenancyGPUShim` simplification** — `object.__setattr__` pattern works; no need to refactor unless we change attribute-access semantics elsewhere.
