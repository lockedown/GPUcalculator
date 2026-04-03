"""Multi-metric optimizer — aggregates Performance, Cost, Complexity, Availability.

v2 improvements:
  1. Benchmark-backed performance: when a finance_benchmark_category is selected,
     the HTML bar_pct scores are blended into the performance axis.
  2. Calibration: decode/prefill tok/s are calibrated against HTML tokenization
     ground-truth via per-GPU multipliers (±15% target).
  3. Hard constraint enforcement: GPUs violating budget, power, or lead-time
     constraints receive a score penalty instead of just a warning.
  4. Rank-based normalization: replaces fragile min-max with rank percentile
     to prevent single outliers from dominating.
  5. Smart sweet-spot: best GPU that passes all hard constraints.
"""

import math
from statistics import mean

from sqlalchemy.orm import Session

from app.models import GPU, Benchmark
from app.schemas.workload import (
    WorkloadInput,
    ConstraintInput,
    GPUResult,
    TopologyResult,
    RackPlanResult,
    ComparisonResponse,
)
from app.engine.performance import calculate_performance, calc_concurrent_users_support, calc_kv_cache_per_user_gb
from app.engine.cost import calc_tco, calc_network_cost
from app.engine.complexity import calc_complexity
from app.engine.availability import calc_availability
from app.engine.calibration import calibrate_decode, calibrate_prefill
from app.engine.rack_planner import plan_rack_layout

# ---------------------------------------------------------------------------
# Constraint violation penalty applied to composite score (0-1 scale)
# ---------------------------------------------------------------------------
HARD_CONSTRAINT_PENALTY = 0.30   # 30% off composite for each hard violation
SOFT_CONSTRAINT_PENALTY = 0.10   # 10% for cooling mismatch (still usable)

# Interconnect → inter-node fabric mapping
GPU_INTERCONNECT_TO_FABRIC: dict[str, str] = {
    "NVLink 4": "IB_NDR",
    "NVLink 5": "IB_XDR",
    "NVLink 5+": "IB_XDR",
    "IF v3": "RoCEv2",
    "IF v4": "RoCEv2",
}


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------
def calc_topology(
    gpu: GPU,
    model_memory_gb: float,
    total_memory_gb: float,
    concurrent_users: int = 1,
    batch_size: int = 1,
    kv_per_user_gb: float = 0.6,
) -> TopologyResult:
    """Determine GPU count and parallelism strategy.

    Includes DP (data-parallel) replicas for throughput scaling when the
    model fits on a single GPU but concurrent load demands more capacity.

    `total_memory_gb` should already include KV cache for ALL concurrent
    sequences (concurrent_users × batch_size × per-sequence KV).

    `kv_per_user_gb` is the pre-computed GQA-aware KV cache per user,
    used by the PCIe path to determine per-card user capacity.
    """
    # Use new memory_gb field if available, otherwise fallback to hbm_capacity_gb
    single_gpu_memory = gpu.memory_gb if gpu.memory_gb is not None else gpu.hbm_capacity_gb

    # --- Rack-scale path (NVL72) ---
    if gpu.is_rack_scale and gpu.rack_gpu_count:
        total_hbm = single_gpu_memory * gpu.rack_gpu_count
        if total_memory_gb <= total_hbm:
            return TopologyResult(
                gpu_count=gpu.rack_gpu_count,
                nodes=1,
                gpus_per_node=gpu.rack_gpu_count,
                parallelism_strategy="NVL72 unified fabric",
                tp_degree=gpu.rack_gpu_count,
                pp_degree=1,
                dp_degree=1,
                effective_bandwidth_gb_s=(
                    gpu.rack_fabric_bw_tb_s * 1000 if gpu.rack_fabric_bw_tb_s else None
                ),
                cross_node_latency_penalty=0.0,
            )

    # --- PCIe-based scaling (RTX PRO 6000 BSE) ---
    if gpu.interconnect_type == "PCIe":
        # PCIe GPUs operate as independent instances (no tensor parallelism).
        # Each card must fit the full model weights; concurrency scales via DP.
        min_gpus_for_model = max(1, math.ceil(model_memory_gb / (single_gpu_memory * 0.85)))

        # How many users fit on one card after weights?
        available_kv_gb = single_gpu_memory * 0.85 - model_memory_gb
        if available_kv_gb > 0 and kv_per_user_gb > 0:
            users_per_card = max(1, int(available_kv_gb / kv_per_user_gb))
        else:
            users_per_card = 1

        total_users = concurrent_users * batch_size
        dp_degree = max(1, math.ceil(total_users / users_per_card))
        gpu_count = max(min_gpus_for_model, dp_degree)

        return TopologyResult(
            gpu_count=gpu_count,
            nodes=math.ceil(gpu_count / 8),
            gpus_per_node=min(gpu_count, 8),
            parallelism_strategy="PCIe independent pools",
            tp_degree=1,
            pp_degree=1,
            dp_degree=dp_degree,
            effective_bandwidth_gb_s=gpu.interconnect_bw_gb_s,
            cross_node_latency_penalty=0.0,  # Independent instances, no cross-GPU comm
        )

    # --- Standard multi-GPU sizing (NVLink-based) ---
    gpus_per_node = gpu.max_gpus_per_node or 8
    min_gpus_for_model = max(1, math.ceil(model_memory_gb / (single_gpu_memory * 0.85)))
    min_gpus_for_workload = max(1, math.ceil(total_memory_gb / (single_gpu_memory * 0.85)))
    capacity_gpus = max(min_gpus_for_model, min_gpus_for_workload)

    # --- DP replicas for throughput scaling ---
    # Each DP replica serves a subset of concurrent users independently.
    # Threshold: 1 DP replica per ~8 concurrent request-streams so that
    # even modest concurrency (e.g. 10 users) triggers additional replicas.
    dp_degree = 1
    total_streams = concurrent_users * batch_size
    if total_streams > 1 and capacity_gpus <= gpus_per_node:
        desired_dp = max(1, math.ceil(total_streams / 8))
        dp_degree = min(desired_dp, 8)  # Cap at 8 DP replicas

    gpu_count = capacity_gpus * dp_degree

    # Round up to node boundaries if multi-node
    nodes = math.ceil(gpu_count / gpus_per_node)
    if nodes > 1:
        gpu_count = nodes * gpus_per_node

    # --- Parallelism strategy ---
    tp = min(capacity_gpus, gpus_per_node)
    pp = max(1, math.ceil(capacity_gpus / gpus_per_node))

    if gpu_count <= 1:
        strategy = "Single GPU"
        tp, pp, dp_degree = 1, 1, 1
    elif dp_degree > 1 and capacity_gpus == 1:
        strategy = f"DP×{dp_degree}"
    elif capacity_gpus <= gpus_per_node:
        strategy = f"TP×{tp}" + (f" DP×{dp_degree}" if dp_degree > 1 else "")
    else:
        strategy = f"TP×{tp} PP×{pp}" + (f" DP×{dp_degree}" if dp_degree > 1 else "")

    # Cross-node latency penalty
    penalty = 0.0
    if nodes > 1:
        penalty = min(0.5, 0.05 * (nodes - 1))

    eff_bw = gpu.interconnect_bw_gb_s
    if eff_bw and nodes > 1:
        eff_bw = eff_bw * 0.7

    return TopologyResult(
        gpu_count=gpu_count,
        nodes=nodes,
        gpus_per_node=min(gpu_count, gpus_per_node),
        parallelism_strategy=strategy,
        tp_degree=tp,
        pp_degree=pp,
        dp_degree=dp_degree,
        effective_bandwidth_gb_s=eff_bw,
        cross_node_latency_penalty=penalty,
    )


# ---------------------------------------------------------------------------
# Benchmark-backed performance score
# ---------------------------------------------------------------------------
def _benchmark_perf_score(
    db: Session, gpu_id: int, category: str
) -> float | None:
    """Return average bar_pct (0-100) for a GPU in a benchmark category.

    Returns None if no benchmarks found for this GPU/category.
    """
    benches = (
        db.query(Benchmark)
        .filter(
            Benchmark.gpu_id == gpu_id,
            Benchmark.workload_category == category,
        )
        .all()
    )
    pcts = [b.bar_pct for b in benches if b.bar_pct is not None]
    return mean(pcts) if pcts else None


def _benchmark_scores_dict(
    db: Session, gpu_id: int, category: str
) -> dict[str, float]:
    """Return {benchmark_name: bar_pct} dict for a GPU in a category."""
    benches = (
        db.query(Benchmark)
        .filter(
            Benchmark.gpu_id == gpu_id,
            Benchmark.workload_category == category,
        )
        .all()
    )
    return {b.benchmark_name: b.bar_pct for b in benches if b.bar_pct is not None}


# ---------------------------------------------------------------------------
# GPU evaluation
# ---------------------------------------------------------------------------
def evaluate_gpu(
    db: Session,
    gpu: GPU,
    workload: WorkloadInput,
    constraints: ConstraintInput,
) -> GPUResult:
    """Evaluate a single GPU against the workload and constraints."""
    warnings: list[str] = []

    # --- Hard Constraint Filtering (Phase 3) ---
    
    # 1. Workload Constraint: RTX PRO 6000 BSE for training/fine-tuning
    if gpu.name == "RTX PRO 6000 BSE":
        if workload.workload_type in ["training", "fine-tuning", "pre-training"]:
            # Return early with a result that will be filtered out
            return GPUResult(
                gpu_id=gpu.id,
                gpu_name=gpu.name,
                gpu_vendor=gpu.vendor,
                warnings=[f"{gpu.name} is not suitable for {workload.workload_type} workloads (inference only)"],
                is_estimated=gpu.is_estimated,
            )
    
    # 2. Infrastructure Constraint: Air cooling vs high-TDP GPUs
    if constraints.cooling_type == "air":
        # Filter out DLC-only and high-TDP GPUs for air-cooled environments
        if gpu.cooling_requirement == "DLC":
            return GPUResult(
                gpu_id=gpu.id,
                gpu_name=gpu.name,
                gpu_vendor=gpu.vendor,
                warnings=[f"{gpu.name} requires liquid cooling (DLC mandatory)"],
                is_estimated=gpu.is_estimated,
            )
        # B200 air cooling is marginal, add warning but allow
        if gpu.name in ["B200 HGX"] and gpu.tdp_watts and gpu.tdp_watts > 900:
            warnings.append(f"{gpu.name} has marginal air cooling support at {gpu.tdp_watts}W TDP")
    
    # 3. 200B Model Constraint: RTX PRO 6000 BSE capacity check
    if workload.model_params_b >= 200 and gpu.name == "RTX PRO 6000 BSE":
        return GPUResult(
            gpu_id=gpu.id,
            gpu_name=gpu.name,
            gpu_vendor=gpu.vendor,
            warnings=[f"{gpu.name} cannot handle {workload.model_params_b}B parameter models (96GB insufficient for 200B+ models)"],
            is_estimated=gpu.is_estimated,
        )

    # --- Performance: first pass with concurrent KV cache for sizing ---
    total_sequences = workload.concurrent_users * workload.batch_size
    moe_kwargs = dict(
        is_moe=workload.is_moe,
        num_experts=workload.num_experts,
        active_experts=workload.active_experts,
    )
    perf_sizing = calculate_performance(
        params_b=workload.model_params_b,
        precision=workload.precision,
        context_length=workload.context_length,
        batch_size=total_sequences,    # KV cache for ALL concurrent sequences
        bf16_tflops=gpu.bf16_tflops or 0,
        mem_bandwidth_tb_s=gpu.mem_bandwidth_tb_s,
        hbm_capacity_gb=gpu.hbm_capacity_gb,
        gpu_count=1,
        **moe_kwargs,
        # New Phase 4 parameters
        memory_gb=gpu.memory_gb,
        memory_type=gpu.memory_type,
        interconnect_type=gpu.interconnect_type,
        supports_fp4=gpu.supports_fp4,
    )

    # --- Topology (uses concurrent-aware memory for sizing) ---
    # Compute per-user KV for topology's PCIe DP scaling
    kv_per_user = calc_kv_cache_per_user_gb(
        workload.context_length, workload.precision, workload.model_params_b
    )
    topo = calc_topology(
        gpu,
        perf_sizing.model_memory_gb,
        perf_sizing.total_memory_required_gb,
        concurrent_users=workload.concurrent_users,
        batch_size=workload.batch_size,
        kv_per_user_gb=kv_per_user,
    )

    # --- Performance: recalculate per-replica metrics with actual GPU count ---
    # Each DP replica handles a fraction of the concurrent sequences.
    sequences_per_replica = max(1, math.ceil(total_sequences / topo.dp_degree))
    perf = calculate_performance(
        params_b=workload.model_params_b,
        precision=workload.precision,
        context_length=workload.context_length,
        batch_size=sequences_per_replica,
        bf16_tflops=gpu.bf16_tflops or 0,
        mem_bandwidth_tb_s=gpu.mem_bandwidth_tb_s,
        hbm_capacity_gb=gpu.hbm_capacity_gb,
        gpu_count=max(1, topo.gpu_count // topo.dp_degree),
        **moe_kwargs,
        # New Phase 4 parameters
        memory_gb=gpu.memory_gb,
        memory_type=gpu.memory_type,
        interconnect_type=gpu.interconnect_type,
        supports_fp4=gpu.supports_fp4,
    )

    # Apply calibration — per-replica throughput
    per_replica_decode = calibrate_decode(
        gpu.name,
        perf.decode_tokens_per_sec * (1.0 - topo.cross_node_latency_penalty),
        workload.precision,
    )
    per_replica_prefill = calibrate_prefill(
        gpu.name,
        perf.prefill_tokens_per_sec * (1.0 - topo.cross_node_latency_penalty),
        workload.precision,
    )

    # Aggregate throughput = sum across all DP replicas
    effective_decode = per_replica_decode * topo.dp_degree
    effective_prefill = per_replica_prefill * topo.dp_degree

    # --- Cost (interconnect-aware) ---
    fabric = GPU_INTERCONNECT_TO_FABRIC.get(
        gpu.intra_node_interconnect or "", "IB_NDR"
    )
    network_cost = calc_network_cost(topo.nodes, fabric) if topo.nodes > 1 else 0
    cost = calc_tco(
        gpu_count=topo.gpu_count,
        gpu_price_usd=gpu.msrp_usd,
        tdp_watts=gpu.tdp_watts,
        tokens_per_sec=effective_decode,
        network_switch_cost_usd=network_cost,
    )

    # --- Complexity ---
    complexity = calc_complexity(
        db, gpu,
        user_cooling=constraints.cooling_type,
        precision=workload.precision,
    )

    # --- Availability ---
    avail = calc_availability(db, gpu, constraints.max_lead_time_weeks)

    # --- Benchmark scores (for display AND scoring) ---
    bench_scores: dict[str, float] = {}
    bench_perf_pct: float | None = None
    if workload.finance_benchmark_category:
        bench_scores = _benchmark_scores_dict(
            db, gpu.id, workload.finance_benchmark_category
        )
        bench_perf_pct = _benchmark_perf_score(
            db, gpu.id, workload.finance_benchmark_category
        )

    # --- Warnings ---
    if gpu.is_estimated:
        warnings.append(f"{gpu.name} specs are estimated (pre-GA)")
    if gpu.cooling_type == "liquid" and constraints.cooling_type == "air":
        if gpu.is_rack_scale:
            warnings.append(f"{gpu.name} is incompatible with air cooling (rack-scale liquid required)")
        else:
            warnings.append(f"{gpu.name} requires liquid cooling")
    if not avail.meets_constraint:
        warnings.append(
            f"{gpu.name} lead time ({avail.lead_time_weeks}w) exceeds constraint"
        )
    if constraints.max_budget_gbp and cost.tco_36m_gbp > constraints.max_budget_gbp:
        warnings.append(
            f"TCO £{cost.tco_36m_gbp:,.0f} exceeds budget £{constraints.max_budget_gbp:,.0f}"
        )
    # Power constraint check
    if constraints.max_power_per_rack_kw and cost.power_kw > constraints.max_power_per_rack_kw:
        warnings.append(
            f"Power {cost.power_kw:.1f}kW exceeds rack limit {constraints.max_power_per_rack_kw}kW"
        )

    # --- Rack planning ---
    rack = plan_rack_layout(
        gpu_name=gpu.name,
        gpu_count=topo.gpu_count,
        tdp_watts=gpu.tdp_watts or 700,
        form_factor=gpu.form_factor or "SXM",
        cooling_type=constraints.cooling_type,
        max_power_per_rack_kw=constraints.max_power_per_rack_kw,
        is_rack_scale=gpu.is_rack_scale or False,
        rack_gpu_count=gpu.rack_gpu_count,
    )
    rack_plan = RackPlanResult(
        total_racks=rack.total_racks,
        servers_per_rack=rack.servers_per_rack,
        gpus_per_rack=rack.gpus_per_rack,
        u_per_server=rack.u_per_server,
        u_utilization_pct=rack.u_utilization_pct,
        power_per_gpu_kw=rack.power_per_gpu_kw,
        power_per_server_kw=rack.power_per_server_kw,
        power_per_rack_kw=rack.power_per_rack_kw,
        total_power_kw=rack.total_power_kw,
        pue_adjusted_power_kw=rack.pue_adjusted_power_kw,
        pdu_tier=rack.pdu_tier,
        pdu_tier_label=rack.pdu_tier_label,
        pdu_headroom_pct=rack.pdu_headroom_pct,
        cooling_type=rack.cooling_type,
        cooling_capacity_kw=rack.cooling_capacity_kw,
        cooling_headroom_pct=rack.cooling_headroom_pct,
        fits_power_constraint=rack.fits_power_constraint,
        fits_cooling=rack.fits_cooling,
        density_warning=rack.density_warning,
    )
    if rack.density_warning:
        warnings.append(rack.density_warning)

    # Max context tokens accounting for concurrent users sharing the VRAM
    max_ctx = perf.max_context_tokens
    if total_sequences > 1:
        # Each concurrent sequence needs its own KV cache slice
        max_ctx = max(0, max_ctx // sequences_per_replica)

    result = GPUResult(
        gpu_id=gpu.id,
        gpu_name=gpu.name,
        gpu_vendor=gpu.vendor,
        is_estimated=gpu.is_estimated or False,
        tokens_per_sec=effective_decode,
        prefill_tokens_per_sec=effective_prefill,
        decode_tokens_per_sec=effective_decode,
        kv_cache_gb=perf_sizing.kv_cache_gb,   # Total KV for all sequences
        max_context_length=max_ctx,
        tco_gbp=cost.tco_36m_gbp,
        capex_gbp=cost.capex_gbp,
        opex_monthly_gbp=cost.opex_monthly_gbp,
        tokens_per_gbp=cost.tokens_per_gbp_per_month,
        complexity_score=complexity.final_score,
        availability_score=avail.score,
        topology=topo,
        rack_plan=rack_plan,
        benchmark_scores=bench_scores if bench_scores else None,
        warnings=warnings,
    )

    # Stash benchmark perf % for composite scoring (not serialised to client)
    result._bench_perf_pct = bench_perf_pct  # type: ignore[attr-defined]
    result._power_kw = cost.power_kw  # type: ignore[attr-defined]
    return result


# ---------------------------------------------------------------------------
# Rank-based normalization
# ---------------------------------------------------------------------------
def _rank_normalize(values: list[float | None], higher_is_better: bool = True) -> list[float]:
    """Convert raw values to 0-1 scores using rank percentile.

    Rank-based normalization is robust to outliers (e.g. NVL72 £3.6M TCO
    doesn't compress all other GPUs into a narrow band).

    Ties receive the same rank.  None values get 0.0.
    """
    n = len(values)
    if n == 0:
        return []

    # Build (value, original_index) pairs, filtering None
    indexed = [(v, i) for i, v in enumerate(values) if v is not None]
    if not indexed:
        return [0.0] * n

    # Sort ascending
    indexed.sort(key=lambda x: x[0])

    # Assign ranks (1-based), handling ties (average rank)
    scores = [0.0] * n
    rank = 1
    i = 0
    while i < len(indexed):
        # Find group of ties
        j = i
        while j < len(indexed) and indexed[j][0] == indexed[i][0]:
            j += 1
        avg_rank = (rank + rank + j - i - 1) / 2.0
        for k in range(i, j):
            orig_idx = indexed[k][1]
            # Normalize rank to 0-1
            if len(indexed) > 1:
                normalized = (avg_rank - 1) / (len(indexed) - 1)
            else:
                normalized = 1.0
            scores[orig_idx] = normalized if higher_is_better else (1.0 - normalized)
        rank += j - i
        i = j

    return scores


# ---------------------------------------------------------------------------
# Constraint enforcement
# ---------------------------------------------------------------------------
def _constraint_penalty(
    result: GPUResult,
    constraints: ConstraintInput,
) -> float:
    """Return total penalty (0-1) for hard constraint violations.

    Each violation applies a fixed penalty.  Penalties stack but cap at 0.9
    so constrained GPUs still appear (just ranked very low).
    """
    penalty = 0.0

    # Budget violation
    if constraints.max_budget_gbp and result.tco_gbp:
        if result.tco_gbp > constraints.max_budget_gbp:
            overshoot = result.tco_gbp / constraints.max_budget_gbp
            penalty += HARD_CONSTRAINT_PENALTY * min(overshoot, 3.0)

    # Power violation
    power_kw = getattr(result, "_power_kw", None)
    if constraints.max_power_per_rack_kw and power_kw:
        if power_kw > constraints.max_power_per_rack_kw:
            penalty += HARD_CONSTRAINT_PENALTY

    # Lead-time violation
    if constraints.max_lead_time_weeks and result.availability_score is not None:
        # availability_score already encodes lead-time, but check hard constraint
        for w in result.warnings:
            if "lead time" in w and "exceeds" in w:
                penalty += HARD_CONSTRAINT_PENALTY
                break

    # Cooling mismatch
    for w in result.warnings:
        if "incompatible with air cooling" in w:
            penalty += HARD_CONSTRAINT_PENALTY  # rack-scale: hard violation
            break
        elif "requires liquid cooling" in w:
            penalty += SOFT_CONSTRAINT_PENALTY  # standard: soft penalty
            break

    return min(penalty, 0.9)


def _passes_all_constraints(result: GPUResult, constraints: ConstraintInput) -> bool:
    """Check if a result passes all hard constraints (for sweet-spot selection)."""
    if constraints.max_budget_gbp and result.tco_gbp:
        if result.tco_gbp > constraints.max_budget_gbp:
            return False
    power_kw = getattr(result, "_power_kw", None)
    if constraints.max_power_per_rack_kw and power_kw:
        if power_kw > constraints.max_power_per_rack_kw:
            return False
    for w in result.warnings:
        if "lead time" in w and "exceeds" in w:
            return False
        if "incompatible with air cooling" in w:
            return False
    return True


# ---------------------------------------------------------------------------
# Composite scoring & ranking
# ---------------------------------------------------------------------------
def normalize_and_rank(
    results: list[GPUResult],
    weights: dict[str, float],
    constraints: ConstraintInput,
) -> list[GPUResult]:
    """Rank-based normalization + benchmark blending + constraint penalties."""
    if not results:
        return results

    n = len(results)

    # --- Rank-normalize each axis ---
    perf_scores = _rank_normalize(
        [r.tokens_per_sec for r in results], higher_is_better=True
    )
    cost_scores = _rank_normalize(
        [r.tco_gbp for r in results], higher_is_better=False  # lower cost = better
    )
    cx_scores = _rank_normalize(
        [r.complexity_score for r in results], higher_is_better=True
    )
    av_scores = _rank_normalize(
        [r.availability_score for r in results], higher_is_better=True
    )

    # --- Benchmark blending ---
    # If a finance benchmark category is selected, blend benchmark bar_pct
    # into the performance axis (50/50 roofline vs benchmark)
    bench_pcts = [getattr(r, "_bench_perf_pct", None) for r in results]
    has_bench = any(b is not None for b in bench_pcts)

    if has_bench:
        bench_scores = _rank_normalize(
            [b if b is not None else None for b in bench_pcts],
            higher_is_better=True,
        )
        # Blend: 50% roofline rank + 50% benchmark rank
        blended_perf = [
            0.5 * perf_scores[i] + 0.5 * bench_scores[i]
            if bench_pcts[i] is not None
            else perf_scores[i]
            for i in range(n)
        ]
    else:
        blended_perf = perf_scores

    # --- Weighted composite ---
    w_perf = weights.get("performance", 0.35)
    w_cost = weights.get("cost", 0.30)
    w_cx = weights.get("complexity", 0.15)
    w_av = weights.get("availability", 0.20)

    for i, r in enumerate(results):
        raw_score = (
            w_perf * blended_perf[i]
            + w_cost * cost_scores[i]
            + w_cx * cx_scores[i]
            + w_av * av_scores[i]
        )

        # Apply constraint penalties
        penalty = _constraint_penalty(r, constraints)
        r.composite_score = round(max(0.0, raw_score * (1.0 - penalty)), 4)

    results.sort(key=lambda r: r.composite_score or 0, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def run_calculation(
    db: Session,
    workload: WorkloadInput,
    constraints: ConstraintInput,
) -> list[GPUResult]:
    """Run sizing calculation for all GPUs."""
    gpus = db.query(GPU).all()
    results = [evaluate_gpu(db, gpu, workload, constraints) for gpu in gpus]
    return normalize_and_rank(results, constraints.metric_weights, constraints)


def run_comparison(
    db: Session,
    workload: WorkloadInput,
    constraints: ConstraintInput,
) -> ComparisonResponse:
    """Run full comparison with smart sweet-spot identification.

    Sweet spot = highest-scoring GPU that passes all hard constraints.
    Falls back to overall top scorer if no GPU passes all constraints.
    """
    results = run_calculation(db, workload, constraints)

    # Smart sweet-spot: best GPU meeting all constraints
    passing = [r for r in results if _passes_all_constraints(r, constraints)]
    if passing:
        sweet_spot = passing[0].gpu_name
    elif results:
        sweet_spot = results[0].gpu_name
    else:
        sweet_spot = None

    return ComparisonResponse(
        workload=workload,
        constraints=constraints,
        results=results,
        sweet_spot_gpu=sweet_spot,
    )
