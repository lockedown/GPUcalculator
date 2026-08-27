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
from app.engine.performance import calculate_performance, calc_kv_cache_per_user_gb
from app.engine.cost import calc_tco, calc_network_cost
from app.engine.complexity import calc_complexity
from app.engine.availability import calc_availability
from app.engine.calibration import calibrate_decode, calibrate_prefill
from app.engine.rack_planner import plan_rack_layout
from app.engine.tenancy import apply_tenancy, TenancyGPUShim
from app.engine.serving_mode import apply_serving_mode, should_recommend_disagg
from app.engine.moe import routing_overhead as moe_routing_overhead

# ---------------------------------------------------------------------------
# Constraint violation penalty applied to composite score (0-1 scale)
# ---------------------------------------------------------------------------
HARD_CONSTRAINT_PENALTY = 0.30   # 30% off composite for each hard violation
SOFT_CONSTRAINT_PENALTY = 0.10   # 10% for cooling mismatch (still usable)


# ---------------------------------------------------------------------------
# Stable codes for machine-readable constraint violations.
# Frontend / API clients should rely on these, not on warning text.
# ---------------------------------------------------------------------------
class Violation:
    BUDGET = "BUDGET_EXCEEDED"
    POWER = "POWER_EXCEEDED"
    LEAD_TIME = "LEAD_TIME_EXCEEDED"
    COOLING_HARD = "COOLING_HARD"             # rack-scale liquid GPU on air-cooled site
    COOLING_SOFT = "COOLING_SOFT"             # standard liquid GPU on air-cooled site
    DLC_REQUIRED = "DLC_REQUIRED"             # GPU is DLC-only; cannot run on air-cooled site
    WORKLOAD_INCOMPATIBLE = "WORKLOAD_INCOMPATIBLE"  # e.g. RTX PRO 6000 BSE for training
    MODEL_TOO_LARGE = "MODEL_TOO_LARGE"       # model exceeds GPU's effective capacity
    MARGINAL_AIR_COOLING = "MARGINAL_AIR_COOLING"
    PRE_GA = "PRE_GA"
    TPOT_MISSED = "TPOT_MISSED"  # advisory: per-user TPOT exceeds target_tpot_ms
    # Disaggregated serving (Sprint 10)
    DISAGG_RECOMMENDED = "DISAGG_RECOMMENDED"  # advisory: workload would benefit from prefill/decode split
    # Multi-tenancy
    MIG_NOT_SUPPORTED = "MIG_NOT_SUPPORTED"        # hard: GPU cannot run MIG
    MIG_PROFILE_REQUIRED = "MIG_PROFILE_REQUIRED"  # hard: MIG mode but no/invalid profile
    MIG_NVLINK_DISABLED = "MIG_NVLINK_DISABLED"    # advisory: TP=1 forced on MIG
    RUNAI_TIME_SLICED = "RUNAI_TIME_SLICED"        # advisory: throughput ÷ tenants

# Codes that constitute a hard pass/fail for sweet-spot filtering
HARD_VIOLATION_CODES: set[str] = {
    Violation.BUDGET,
    Violation.POWER,
    Violation.LEAD_TIME,
    Violation.COOLING_HARD,
    Violation.DLC_REQUIRED,
    Violation.WORKLOAD_INCOMPATIBLE,
    Violation.MODEL_TOO_LARGE,
    Violation.MIG_NOT_SUPPORTED,
    Violation.MIG_PROFILE_REQUIRED,
}

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
# Minimum acceptable decode tok/s per user — below this, the experience is
# unusably slow.  DP replicas are added until each user can reach this rate.
MIN_DECODE_TPS_PER_USER = 10.0


def _next_power_of_two(n: int) -> int:
    """Round up to the next power of two (1, 2, 4, 8, …).

    TP all-reduce primitives (NCCL ring/tree) are most efficient at power-of-2
    GPU counts; non-pow2 TP degrees are rare in production deployments.
    """
    if n <= 1:
        return 1
    p = 1
    while p < n:
        p *= 2
    return p


def calc_topology(
    gpu: GPU,
    model_memory_gb: float,
    total_memory_gb: float,
    concurrent_users: int = 1,
    batch_size: int = 1,
    kv_per_user_gb: float = 0.6,
    per_gpu_decode_tps: float = 0.0,
) -> TopologyResult:
    """Determine GPU count and parallelism strategy.

    Includes DP (data-parallel) replicas for throughput scaling when the
    model fits on a single GPU but concurrent load demands more capacity.

    `total_memory_gb` should already include KV cache for ALL concurrent
    sequences (concurrent_users × batch_size × per-sequence KV).

    `kv_per_user_gb` is the pre-computed GQA-aware KV cache per user,
    used by the PCIe path to determine per-card user capacity.

    `per_gpu_decode_tps` is the calibrated single-GPU decode throughput,
    used to compute throughput-aware DP scaling so each user gets at
    least MIN_DECODE_TPS_PER_USER.
    """
    # Use new memory_gb field if available, otherwise fallback to hbm_capacity_gb
    single_gpu_memory = gpu.memory_gb if gpu.memory_gb is not None else gpu.hbm_capacity_gb

    # --- Rack-scale path (NVL72 / Helios) ---
    if gpu.is_rack_scale and gpu.rack_gpu_count:
        rack_gpu_count = gpu.rack_gpu_count
        total_hbm = single_gpu_memory * rack_gpu_count
        total_streams = concurrent_users * batch_size

        # How many racks does memory alone require? A rack-scale system is
        # bought/deployed in whole-rack units — there's no partial-rack TP,
        # so once one rack's aggregate HBM is exceeded the next unit is a
        # whole additional rack (DP across racks), not a bigger single rack.
        dp_memory = max(1, math.ceil(total_memory_gb / total_hbm)) if total_hbm > 0 else 1

        # Throughput-aware: how many racks keep each concurrent stream at
        # MIN_DECODE_TPS_PER_USER. `per_gpu_decode_tps` here is already the
        # calibrated *whole-rack* single-stream decode figure (the caller
        # sizes it at gpu_count=rack_gpu_count, matching how NVL72/Helios
        # calibration anchors are themselves defined at full-rack scale —
        # see calibration.py's RACK_SCALE_REFERENCE_GPUS) — no further
        # multiplication by rack_gpu_count here, that would double-count it.
        dp_throughput = 1
        if per_gpu_decode_tps > 0 and total_streams > 0:
            required_tps = total_streams * MIN_DECODE_TPS_PER_USER
            dp_throughput = max(1, math.ceil(required_tps / per_gpu_decode_tps))

        num_racks = max(dp_memory, dp_throughput)
        gpu_count = rack_gpu_count * num_racks

        strategy = (
            "NVL72 unified fabric" if num_racks == 1
            else f"NVL72 unified fabric ×{num_racks} racks (DP)"
        )
        # Inter-rack network hop cost — same treatment as inter-node IB hops
        # on the standard multi-GPU path below.
        penalty = min(0.5, 0.05 * (num_racks - 1)) if num_racks > 1 else 0.0

        return TopologyResult(
            gpu_count=gpu_count,
            nodes=num_racks,
            gpus_per_node=rack_gpu_count,
            parallelism_strategy=strategy,
            tp_degree=rack_gpu_count,
            pp_degree=1,
            dp_degree=num_racks,
            effective_bandwidth_gb_s=(
                gpu.rack_fabric_bw_tb_s * 1000 if gpu.rack_fabric_bw_tb_s else None
            ),
            cross_node_latency_penalty=penalty,
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
        dp_memory = max(1, math.ceil(total_users / users_per_card))

        # Throughput-aware DP: ensure each user gets MIN_DECODE_TPS_PER_USER
        dp_throughput = 1
        if per_gpu_decode_tps > 0 and total_users > 0:
            required_tps = total_users * MIN_DECODE_TPS_PER_USER
            dp_throughput = max(1, math.ceil(required_tps / per_gpu_decode_tps))

        dp_degree = max(dp_memory, dp_throughput)
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
    available_per_gpu = single_gpu_memory * 0.85  # 15% reserve for activations/buffers

    total_streams = concurrent_users * batch_size

    # Step 1: minimum GPUs for the model weights alone (TP/PP capacity floor)
    min_gpus_for_model = max(1, math.ceil(model_memory_gb / available_per_gpu))

    # Step 2: estimate DP using the model-only capacity, so per-replica memory
    # can then be sized correctly for the *fraction* of streams each replica handles
    initial_replica_capacity = min_gpus_for_model
    dp_degree = 1
    if total_streams > 1 and initial_replica_capacity <= gpus_per_node:
        replica_tps = (
            per_gpu_decode_tps * initial_replica_capacity if per_gpu_decode_tps > 0 else 0
        )
        if replica_tps > 0:
            required_tps = total_streams * MIN_DECODE_TPS_PER_USER
            dp_degree = max(1, math.ceil(required_tps / replica_tps))
        else:
            dp_degree = max(1, math.ceil(total_streams / 8))

    # Step 3: per-replica memory (model + KV for this replica's stream slice)
    sequences_per_replica = max(1, math.ceil(total_streams / dp_degree))
    per_replica_memory_gb = model_memory_gb + sequences_per_replica * kv_per_user_gb
    capacity_gpus = max(
        min_gpus_for_model,
        math.ceil(per_replica_memory_gb / available_per_gpu),
    )

    # Step 4: round single-node TP up to a power of 2 for efficient all-reduce.
    # (Multi-node configs use TP=gpus_per_node intra-node + PP across nodes.)
    if capacity_gpus <= gpus_per_node:
        capacity_gpus = min(_next_power_of_two(capacity_gpus), gpus_per_node)

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

    # Intra-node fabric topology shapes effective bandwidth.
    #   nvswitch     — full bisection across the baseboard (HGX/DGX 8-GPU).
    #   nvl_fabric   — NVL72 rack-scale; effectively single-hop at TP up to 72.
    #   point_to_point — direct NVLink/IF links, no switch. AMD MI3xx-series and
    #                    legacy NVLink boards take a derate at TP > 4 because
    #                    the cube-mesh adds an extra hop for non-adjacent peers.
    #   none / PCIe  — handled by the PCIe branch above; never reached here.
    nvlink_topology = getattr(gpu, "nvlink_topology", None)
    eff_bw = gpu.interconnect_bw_gb_s
    if eff_bw:
        if nodes > 1:
            eff_bw = eff_bw * 0.7  # cross-node IB hop cost (existing behaviour)
        if nvlink_topology == "point_to_point" and tp > 4:
            # Non-adjacent peers traverse 2 hops on a hyper-cube mesh; the
            # observed all-reduce throughput is ~85% of the link-rate baseline
            # (NCCL/RCCL benchmarks on MI300X 8-GPU OAM trays).
            eff_bw = eff_bw * 0.85
        elif nvlink_topology == "point_to_point" and nodes > 1:
            penalty = min(0.5, penalty + 0.05)

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
# GPU evaluation — phase helpers
# ---------------------------------------------------------------------------
def _apply_hard_filters(
    gpu: GPU,
    workload: WorkloadInput,
    constraints: ConstraintInput,
) -> tuple[GPUResult | None, list[str], list[str]]:
    """Run the three hard short-circuit checks (workload-incompatible, DLC
    required, model-too-large for RTX PRO).

    Returns ``(early_result, warnings, codes)``. When ``early_result`` is not
    None the caller should return it immediately; otherwise it should continue
    with the populated ``warnings`` / ``codes`` (which carry any soft advisory
    like ``MARGINAL_AIR_COOLING``).
    """
    warnings: list[str] = []
    codes: list[str] = []

    # 1. Workload constraint: RTX PRO 6000 BSE is inference-only.
    if gpu.name == "RTX PRO 6000 BSE" and workload.workload_type in ("training", "fine-tuning", "pre-training"):
        return (
            GPUResult(
                gpu_id=gpu.id,
                gpu_name=gpu.name,
                gpu_vendor=gpu.vendor,
                warnings=[f"{gpu.name} is not suitable for {workload.workload_type} workloads (inference only)"],
                violation_codes=[Violation.WORKLOAD_INCOMPATIBLE],
                is_estimated=gpu.is_estimated,
            ),
            warnings,
            codes,
        )

    # 2. Infrastructure constraint: air cooling can't host DLC-only GPUs.
    if constraints.cooling_type == "air":
        if gpu.cooling_requirement == "DLC":
            return (
                GPUResult(
                    gpu_id=gpu.id,
                    gpu_name=gpu.name,
                    gpu_vendor=gpu.vendor,
                    warnings=[f"{gpu.name} requires liquid cooling (DLC mandatory)"],
                    violation_codes=[Violation.DLC_REQUIRED],
                    is_estimated=gpu.is_estimated,
                ),
                warnings,
                codes,
            )
        # B200 on air is marginal, advisory only.
        if gpu.name == "B200 HGX" and gpu.tdp_watts and gpu.tdp_watts > 900:
            warnings.append(f"{gpu.name} has marginal air cooling support at {gpu.tdp_watts}W TDP")
            codes.append(Violation.MARGINAL_AIR_COOLING)

    # 3. Memory constraint: RTX PRO can't host 200B+ models.
    if workload.model_params_b >= 200 and gpu.name == "RTX PRO 6000 BSE":
        return (
            GPUResult(
                gpu_id=gpu.id,
                gpu_name=gpu.name,
                gpu_vendor=gpu.vendor,
                warnings=[f"{gpu.name} cannot handle {workload.model_params_b}B parameter models (96GB insufficient for 200B+ models)"],
                violation_codes=[Violation.MODEL_TOO_LARGE],
                is_estimated=gpu.is_estimated,
            ),
            warnings,
            codes,
        )

    return None, warnings, codes


def _compute_latency(
    workload: WorkloadInput,
    effective_decode: float,
    effective_prefill: float,
    total_sequences: int,
) -> tuple[float | None, float | None, float]:
    """Return ``(ttft_ms, tpot_ms, per_user_decode_tps)`` for the workload.

    Aggregate throughput is shared across ``total_sequences`` concurrent users,
    so per-user rate = aggregate ÷ total_sequences. TTFT is wall-clock time to
    chew through one user's prompt; TPOT is the gap between successive output
    tokens for one user. Caller decides whether to emit ``TPOT_MISSED``.
    """
    user_count = max(1, total_sequences)
    per_user_decode_tps = effective_decode / user_count if effective_decode > 0 else 0.0
    per_user_prefill_tps = effective_prefill / user_count if effective_prefill > 0 else 0.0
    tpot_ms = 1000.0 / per_user_decode_tps if per_user_decode_tps > 0 else None
    ttft_ms = (
        workload.context_length * 1000.0 / per_user_prefill_tps
        if per_user_prefill_tps > 0
        else None
    )
    return ttft_ms, tpot_ms, per_user_decode_tps


def _compute_moe_surfacing(
    workload: WorkloadInput,
    moe_overhead: float,
) -> tuple[float | None, float | None, float | None]:
    """Return ``(active_param_fraction, effective_bw_per_token_gb, routing_overhead_pct)``
    for MoE workloads. All-None for dense workloads.

    ``effective_bw_per_token_gb`` is the active-expert weight bytes streamed
    per output token — the bandwidth-bound denominator visible to the customer.
    """
    if not workload.is_moe or workload.num_experts <= 0:
        return None, None, None
    # Imported here to avoid a circular import at module load time.
    from app.engine.performance import PRECISION_BYTES
    active_fraction = workload.active_experts / workload.num_experts
    bytes_per_param = PRECISION_BYTES.get(workload.precision, 2.0)
    effective_bw_gb = workload.model_params_b * active_fraction * bytes_per_param
    overhead_pct = round(moe_overhead * 100, 1) if moe_overhead > 0 else 0.0
    return active_fraction, effective_bw_gb, overhead_pct


def _collect_constraint_advisories(
    gpu: GPU,
    constraints: ConstraintInput,
    cost,
    avail,
) -> tuple[list[str], list[str]]:
    """Return ``(warnings, codes)`` for the post-cost / availability checks
    (cooling, lead-time, budget, power, PRE_GA).
    """
    warnings: list[str] = []
    codes: list[str] = []

    if gpu.is_estimated:
        warnings.append(f"{gpu.name} specs are estimated (pre-GA)")
        codes.append(Violation.PRE_GA)
    if gpu.cooling_type == "liquid" and constraints.cooling_type == "air":
        if gpu.is_rack_scale:
            warnings.append(f"{gpu.name} is incompatible with air cooling (rack-scale liquid required)")
            codes.append(Violation.COOLING_HARD)
        else:
            warnings.append(f"{gpu.name} requires liquid cooling")
            codes.append(Violation.COOLING_SOFT)
    if not avail.meets_constraint:
        warnings.append(f"{gpu.name} lead time ({avail.lead_time_weeks}w) exceeds constraint")
        codes.append(Violation.LEAD_TIME)
    if constraints.max_budget_usd and cost.tco_36m_usd > constraints.max_budget_usd:
        warnings.append(
            f"TCO ${cost.tco_36m_usd:,.0f} exceeds budget ${constraints.max_budget_usd:,.0f}"
        )
        codes.append(Violation.BUDGET)
    if constraints.max_power_per_rack_kw and cost.power_kw > constraints.max_power_per_rack_kw:
        warnings.append(
            f"Power {cost.power_kw:.1f}kW exceeds rack limit {constraints.max_power_per_rack_kw}kW"
        )
        codes.append(Violation.POWER)

    return warnings, codes


# ---------------------------------------------------------------------------
# GPU evaluation — orchestrator
# ---------------------------------------------------------------------------
def evaluate_gpu(
    db: Session,
    gpu: GPU,
    workload: WorkloadInput,
    constraints: ConstraintInput,
) -> GPUResult:
    """Evaluate a single GPU against the workload and constraints."""
    early, warnings, codes = _apply_hard_filters(gpu, workload, constraints)
    if early is not None:
        return early

    # --- Multi-tenancy: resolve per-tenant effective specs ---
    # apply_tenancy returns the per-tenant view of compute/memory/bandwidth.
    # Hard errors (MIG on Blackwell, missing MIG profile) short-circuit;
    # advisory codes (MIG_NVLINK_DISABLED, RUNAI_TIME_SLICED) flow through.
    tenancy = apply_tenancy(
        gpu,
        mode=workload.multi_tenancy_mode,
        mig_profile=workload.mig_profile,
        tenants=workload.tenants,
    )
    if tenancy.error_codes:
        msgs = []
        if "MIG_NOT_SUPPORTED" in tenancy.error_codes:
            msgs.append(f"{gpu.name} ({gpu.generation}) does not support MIG partitioning")
        if "MIG_PROFILE_REQUIRED" in tenancy.error_codes:
            msgs.append("MIG mode requires a valid mig_profile")
        return GPUResult(
            gpu_id=gpu.id,
            gpu_name=gpu.name,
            gpu_vendor=gpu.vendor,
            warnings=msgs,
            violation_codes=list(tenancy.error_codes),
            is_estimated=gpu.is_estimated,
        )

    # Use the shim wherever calc_topology / calculate_performance / cost-calc
    # read GPU spec fields directly.  For "dedicated" the shim is a no-op
    # passthrough (overrides equal real values), so we always wrap.
    eff_gpu = TenancyGPUShim(gpu, tenancy)

    # --- Performance: first pass with concurrent KV cache for sizing ---
    total_sequences = workload.concurrent_users * workload.batch_size
    moe_kwargs = dict(
        is_moe=workload.is_moe,
        num_experts=workload.num_experts,
        active_experts=workload.active_experts,
    )
    # Rack-scale GPUs (NVL72 / Helios) are never deployed as a single card —
    # size the sizing pass at a whole rack (matching how their calibration
    # anchors are themselves defined, see calibration.py's
    # RACK_SCALE_REFERENCE_GPUS) so calibrated_single_decode below means
    # "one rack's single-stream decode", not "one GPU's".
    sizing_gpu_count = (
        gpu.rack_gpu_count if (gpu.is_rack_scale and gpu.rack_gpu_count) else 1
    )
    perf_sizing = calculate_performance(
        params_b=workload.model_params_b,
        precision=workload.precision,
        context_length=workload.context_length,
        batch_size=total_sequences,    # KV cache for ALL concurrent sequences
        bf16_tflops=eff_gpu.bf16_tflops or 0,
        mem_bandwidth_tb_s=eff_gpu.mem_bandwidth_tb_s,
        hbm_capacity_gb=eff_gpu.hbm_capacity_gb,
        gpu_count=sizing_gpu_count,
        **moe_kwargs,
        # New Phase 4 parameters
        memory_gb=eff_gpu.memory_gb,
        memory_type=gpu.memory_type,
        interconnect_type=eff_gpu.interconnect_type,
        supports_fp4=gpu.supports_fp4,
    )

    # --- Topology (uses concurrent-aware memory for sizing) ---
    # Compute per-user KV for topology's PCIe DP scaling
    kv_per_user = calc_kv_cache_per_user_gb(
        workload.context_length, workload.precision, workload.model_params_b
    )

    # Calibrated single-GPU (or single-rack, see sizing_gpu_count above)
    # decode throughput for throughput-aware DP scaling.
    raw_single_gpu_decode = perf_sizing.decode_tokens_per_sec
    calibrated_single_decode = calibrate_decode(
        gpu.name, raw_single_gpu_decode, workload.precision
    )

    topo = calc_topology(
        eff_gpu,
        perf_sizing.model_memory_gb,
        perf_sizing.total_memory_required_gb,
        concurrent_users=workload.concurrent_users,
        batch_size=workload.batch_size,
        kv_per_user_gb=kv_per_user,
        per_gpu_decode_tps=calibrated_single_decode,
    )

    # Disaggregated prefill/decode view — mirrors in colocated mode, splits
    # 30/70 in disaggregated mode. Sizing/cost are unchanged either way.
    apply_serving_mode(topo, workload.serving_mode)
    if workload.serving_mode == "colocated" and should_recommend_disagg(workload):
        warnings.append(
            "Workload may benefit from disaggregated prefill/decode "
            f"({workload.concurrent_users} users × {workload.context_length} ctx — "
            "Dynamo / DeepSeek-V3 regime)"
        )
        codes.append(Violation.DISAGG_RECOMMENDED)

    # --- Performance: recalculate per-replica metrics with actual GPU count ---
    # Each DP replica handles a fraction of the concurrent sequences.
    sequences_per_replica = max(1, math.ceil(total_sequences / topo.dp_degree))
    perf = calculate_performance(
        params_b=workload.model_params_b,
        precision=workload.precision,
        context_length=workload.context_length,
        batch_size=sequences_per_replica,
        bf16_tflops=eff_gpu.bf16_tflops or 0,
        mem_bandwidth_tb_s=eff_gpu.mem_bandwidth_tb_s,
        hbm_capacity_gb=eff_gpu.hbm_capacity_gb,
        gpu_count=max(1, topo.gpu_count // topo.dp_degree),
        **moe_kwargs,
        # New Phase 4 parameters
        memory_gb=eff_gpu.memory_gb,
        memory_type=gpu.memory_type,
        interconnect_type=eff_gpu.interconnect_type,
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

    # MoE all-to-all routing overhead — applied to decode only (per-token cost).
    # This is on top of calibration (which is dense-Llama-3-70B based and does
    # not reflect MoE dispatch costs).
    moe_overhead = moe_routing_overhead(
        workload.num_experts if workload.is_moe else 1,
        workload.active_experts if workload.is_moe else 1,
        topo.nodes,
        topo.gpu_count,
    )
    if moe_overhead > 0:
        effective_decode *= 1.0 - moe_overhead

    # Run:ai time-slicing — each tenant gets aggregate ÷ tenants. MIG is
    # already accounted for via the spec downscaling above (compute and
    # bandwidth fractions), so its divisor stays 1.0.
    if tenancy.throughput_divisor > 1.0:
        effective_decode /= tenancy.throughput_divisor
        effective_prefill /= tenancy.throughput_divisor

    # Per-tenant view = aggregate after tenancy adjustments. For MIG it equals
    # effective_decode (one tenant per slice). For Run:ai it's the slice each
    # of N tenants gets. For dedicated it equals aggregate (single tenant).
    per_tenant_decode_tps = effective_decode if tenancy.tenancy_mode_applied != "dedicated" else None

    # Tenancy advisory codes always flow through to the result.
    for advisory in tenancy.advisory_codes:
        if advisory not in codes:
            codes.append(advisory)
            if advisory == "MIG_NVLINK_DISABLED":
                warnings.append(
                    f"{gpu.name} MIG instances cannot share NVLink — TP forced to 1"
                )
            elif advisory == "RUNAI_TIME_SLICED":
                warnings.append(
                    f"Run:ai time-slicing across {workload.tenants} tenants — "
                    f"per-tenant throughput is aggregate ÷ {workload.tenants}"
                )

    # --- Per-user latency (TTFT, TPOT) ---
    ttft_ms, tpot_ms, per_user_decode_tps = _compute_latency(
        workload, effective_decode, effective_prefill, total_sequences
    )
    if (
        constraints.target_tpot_ms is not None
        and tpot_ms is not None
        and tpot_ms > constraints.target_tpot_ms
    ):
        warnings.append(
            f"Per-user TPOT {tpot_ms:.0f}ms exceeds target {constraints.target_tpot_ms}ms"
        )
        codes.append(Violation.TPOT_MISSED)

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
        cooling_type=gpu.cooling_type,
        amortization_months=constraints.amortization_months,
        colo_usd_per_kw_per_month=constraints.colo_usd_per_kw_per_month,
        hw_support_pct_of_capex_per_year=constraints.hw_support_pct_of_capex_per_year,
        software_usd_per_gpu_per_year=constraints.software_usd_per_gpu_per_year,
        grid_carbon_intensity_g_kwh=constraints.grid_carbon_intensity_g_kwh,
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

    # --- Warnings + structured violation codes ---
    advisory_warnings, advisory_codes = _collect_constraint_advisories(
        gpu, constraints, cost, avail
    )
    warnings.extend(advisory_warnings)
    codes.extend(advisory_codes)

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
    # Note: rack-density warnings stay narrative-only — they're a hint to the
    # user, not a constraint. Add a code here later if they become filterable.

    # Max context tokens accounting for concurrent users sharing the VRAM
    max_ctx = perf.max_context_tokens
    if total_sequences > 1:
        # Each concurrent sequence needs its own KV cache slice
        max_ctx = max(0, max_ctx // sequences_per_replica)

    # MoE-specific surfacing — only meaningful when is_moe.
    moe_active_param_fraction, moe_effective_bw_per_token_gb, moe_routing_overhead_pct = (
        _compute_moe_surfacing(workload, moe_overhead)
    )

    # Per-tenant KV cache: under MIG, the slice's KV envelope is what matters
    # (not the aggregate); under Run:ai the full GPU KV is shared, but each
    # tenant pays for their own slice.
    per_tenant_kv = (
        perf_sizing.kv_cache_gb / max(1, tenancy.instances_per_gpu)
        if tenancy.tenancy_mode_applied != "dedicated"
        else None
    )

    result = GPUResult(
        gpu_id=gpu.id,
        gpu_name=gpu.name,
        gpu_vendor=gpu.vendor,
        is_estimated=gpu.is_estimated or False,
        tokens_per_sec=effective_decode,
        prefill_tokens_per_sec=effective_prefill,
        decode_tokens_per_sec=effective_decode,
        ttft_ms=ttft_ms,
        tpot_ms=tpot_ms,
        per_user_decode_tps=per_user_decode_tps if per_user_decode_tps > 0 else None,
        tenancy_mode_applied=(
            tenancy.tenancy_mode_applied
            if tenancy.tenancy_mode_applied != "dedicated"
            else None
        ),
        tenants_per_gpu=(
            tenancy.instances_per_gpu
            if tenancy.tenancy_mode_applied != "dedicated"
            else None
        ),
        per_tenant_decode_tps=per_tenant_decode_tps,
        per_tenant_kv_cache_gb=per_tenant_kv,
        moe_active_param_fraction=moe_active_param_fraction,
        moe_effective_bw_per_token_gb=moe_effective_bw_per_token_gb,
        moe_routing_overhead_pct=moe_routing_overhead_pct,
        kv_cache_gb=perf_sizing.kv_cache_gb,   # Total KV for all sequences
        max_context_length=max_ctx,
        tco_usd=cost.tco_36m_usd,
        carbon_kg_per_year=cost.carbon_kg_per_year,
        capex_usd=cost.capex_usd,
        opex_monthly_usd=cost.opex_monthly_usd,
        opex_breakdown=cost.opex_breakdown,
        tokens_per_usd=cost.tokens_per_usd_per_month,
        complexity_score=complexity.final_score,
        availability_score=avail.score,
        topology=topo,
        rack_plan=rack_plan,
        benchmark_scores=bench_scores if bench_scores else None,
        warnings=warnings,
        violation_codes=codes,
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

    Rank-based normalization is robust to outliers (e.g. NVL72 $4M+ TCO
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
    """Return total penalty (0-1) for constraint violations.

    Reads structured ``violation_codes`` populated by ``evaluate_gpu``. Each
    hard violation applies ``HARD_CONSTRAINT_PENALTY``; cooling soft violation
    applies ``SOFT_CONSTRAINT_PENALTY``. Budget penalty scales with overshoot
    magnitude. Total caps at 0.9 so constrained GPUs still appear (ranked very
    low) instead of disappearing.
    """
    codes = set(result.violation_codes)
    penalty = 0.0

    # Budget — scale with overshoot ratio
    if Violation.BUDGET in codes and constraints.max_budget_usd and result.tco_usd:
        overshoot = result.tco_usd / constraints.max_budget_usd
        penalty += HARD_CONSTRAINT_PENALTY * min(overshoot, 3.0)

    if Violation.POWER in codes:
        penalty += HARD_CONSTRAINT_PENALTY

    if Violation.LEAD_TIME in codes:
        penalty += HARD_CONSTRAINT_PENALTY

    # Cooling: COOLING_HARD (rack-scale) > COOLING_SOFT (standard liquid GPU)
    if Violation.COOLING_HARD in codes:
        penalty += HARD_CONSTRAINT_PENALTY
    elif Violation.COOLING_SOFT in codes:
        penalty += SOFT_CONSTRAINT_PENALTY

    return min(penalty, 0.9)


def _passes_all_constraints(result: GPUResult, constraints: ConstraintInput) -> bool:
    """True if no hard violations are present on this result.

    Hard violations are listed in ``HARD_VIOLATION_CODES``. Soft / advisory
    codes (COOLING_SOFT, MARGINAL_AIR_COOLING, PRE_GA) do not disqualify.
    """
    return not (set(result.violation_codes) & HARD_VIOLATION_CODES)


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
        [r.tco_usd for r in results], higher_is_better=False  # lower cost = better
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


def _explain_sweet_spot(
    chosen: GPUResult,
    results: list[GPUResult],
    passing: list[GPUResult],
    constraints: ConstraintInput,
) -> list[str]:
    """Return up to 3 short reasons explaining why ``chosen`` was picked.

    Reasons are ordered by customer-meeting relevance: cost-efficiency first
    (the $/tok argument lands in budget conversations), then user-perceived
    latency (TTFT/TPOT), then constraint scarcity, then the strongest score
    axis. Falls back to a generic "highest composite score" line if nothing
    distinctive applies.
    """
    if not results or chosen is None:
        return []

    reasons: list[str] = []

    # 1. Cost efficiency — best tokens/$/mo across the catalogue.
    tokens_per_usd = [(r, r.tokens_per_usd) for r in results if r.tokens_per_usd]
    if tokens_per_usd:
        best = max(tokens_per_usd, key=lambda x: x[1])[0]
        if best.gpu_name == chosen.gpu_name:
            reasons.append(
                f"Best tokens/$/mo across the catalogue ({chosen.tokens_per_usd:,.0f})"
            )

    # 2. User-perceived latency — only meaningful when a target was set or
    # when this GPU is decisively faster than the field.
    ttfts = [(r, r.ttft_ms) for r in results if r.ttft_ms is not None]
    if ttfts and len(reasons) < 3:
        best_ttft = min(ttfts, key=lambda x: x[1])[0]
        if best_ttft.gpu_name == chosen.gpu_name and chosen.ttft_ms is not None:
            reasons.append(f"Lowest TTFT in field ({chosen.ttft_ms:.0f} ms)")

    tpots = [(r, r.tpot_ms) for r in results if r.tpot_ms is not None]
    if tpots and len(reasons) < 3:
        best_tpot = min(tpots, key=lambda x: x[1])[0]
        if best_tpot.gpu_name == chosen.gpu_name and chosen.tpot_ms is not None:
            target = constraints.target_tpot_ms
            target_note = (
                f" (within {target} ms target)"
                if target is not None and chosen.tpot_ms <= target
                else ""
            )
            reasons.append(f"Lowest TPOT in field ({chosen.tpot_ms:.1f} ms{target_note})")

    # 3. Constraint scarcity — high-signal when only one or two pass.
    if len(reasons) < 3 and len(passing) == 1 and chosen.gpu_name == passing[0].gpu_name:
        reasons.append("Only candidate passing all hard constraints")
    elif len(reasons) < 3 and len(passing) <= 3 and chosen in passing:
        # Two or three pass — note this when nothing else is distinctive yet.
        if not reasons:
            reasons.append(f"One of {len(passing)} passing all hard constraints")

    # 4. Score-axis dominance — best on whichever axis has the highest weight
    # AND on which this GPU genuinely leads. Prevents "best perf" being a
    # rounding tie. Skipped if we already have 3 reasons.
    if len(reasons) < 3:
        axis_lookup = {
            "performance": ("perf", "decode_tokens_per_sec"),
            "cost": ("cost", "tco_usd"),
            "complexity": ("complexity", "complexity_score"),
            "availability": ("availability", "availability_score"),
        }
        # Pick the axis with the largest user weight; tie-break alphabetically.
        weights = constraints.metric_weights
        sorted_axes = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))
        for axis, _w in sorted_axes:
            if axis not in axis_lookup:
                continue
            label, attr = axis_lookup[axis]
            values = [(r, getattr(r, attr)) for r in results if getattr(r, attr) is not None]
            if not values:
                continue
            # Cost is "lower is better"; the others are "higher is better".
            if axis == "cost":
                best = min(values, key=lambda x: x[1])[0]
            else:
                best = max(values, key=lambda x: x[1])[0]
            if best.gpu_name == chosen.gpu_name:
                reasons.append(f"Strongest {label} score in the weighted ranking")
                break

    # 5. Composite-score fallback — never leave the field empty.
    if not reasons:
        reasons.append(
            f"Highest composite score ({chosen.composite_score:.3f}) under the configured weights"
        )

    return reasons[:3]


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
        chosen = passing[0]
    elif results:
        chosen = results[0]
    else:
        chosen = None

    sweet_spot = chosen.gpu_name if chosen else None
    reasons = _explain_sweet_spot(chosen, results, passing, constraints) if chosen else []

    return ComparisonResponse(
        workload=workload,
        constraints=constraints,
        results=results,
        sweet_spot_gpu=sweet_spot,
        sweet_spot_reasons=reasons,
    )
