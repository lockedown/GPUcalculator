"""Disaggregated prefill/decode split (Sprint 10 — observability v1).

Default Dynamo / DeepSeek-V3 split — observed to land near 30% prefill / 70%
decode for chat-style traffic. Long-prompt or RAG workloads tilt toward 50/50;
v2 will compute the optimal ratio from prefill/decode demand. v1 uses the
fixed default and surfaces it as a recommendation; cost + rack are still
computed against ``topo.gpu_count``.
"""

from app.schemas.workload import TopologyResult, WorkloadInput

# Default split ratio applied in disaggregated mode.
DISAGG_PREFILL_SHARE = 0.30

# Heuristic thresholds for emitting DISAGG_RECOMMENDED in colocated mode.
# Both must fire — concurrent_users alone is decode pressure; context_length
# alone is prefill pressure. Together they're the canonical "split helps"
# signal that matches the public Dynamo / DeepSeek-V3 deployment pattern.
DISAGG_USERS_THRESHOLD = 32
DISAGG_CONTEXT_THRESHOLD = 8192


def apply_serving_mode(topo: TopologyResult, serving_mode: str) -> TopologyResult:
    """Populate prefill/decode role fields on ``topo`` in place.

    In 'colocated' mode both pools mirror the unified topology. In
    'disaggregated' mode the GPU budget is split 30/70 (prefill/decode) as a
    recommendation. Returns the same TopologyResult for chaining.
    """
    topo.serving_mode = serving_mode
    if serving_mode == "disaggregated" and topo.gpu_count >= 2:
        prefill_n = max(1, round(topo.gpu_count * DISAGG_PREFILL_SHARE))
        decode_n = max(1, topo.gpu_count - prefill_n)
        topo.prefill_gpu_count = prefill_n
        topo.decode_gpu_count = decode_n
        topo.prefill_role_strategy = f"Prefill pool · {prefill_n}× GPU (compute-dense)"
        topo.decode_role_strategy = f"Decode pool · {decode_n}× GPU (bandwidth-dense)"
    else:
        # Colocated, or disagg with too few GPUs to split meaningfully — mirror.
        topo.prefill_gpu_count = topo.gpu_count
        topo.decode_gpu_count = topo.gpu_count
        topo.prefill_role_strategy = topo.parallelism_strategy
        topo.decode_role_strategy = topo.parallelism_strategy
    return topo


def should_recommend_disagg(workload: WorkloadInput) -> bool:
    """True when the workload sits in the disaggregation sweet spot.

    Disaggregation is operationally heavy (separate KV transfer, two pools to
    schedule), so the advisory only fires when both prefill cost (long context)
    and decode pressure (many concurrent users) are present.
    """
    return (
        workload.concurrent_users >= DISAGG_USERS_THRESHOLD
        and workload.context_length >= DISAGG_CONTEXT_THRESHOLD
    )
