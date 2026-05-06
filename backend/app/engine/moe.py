"""MoE routing-overhead model (Sprint 9a).

Public MoE deployments (Mixtral 8×22B, DeepSeek-V3, Qwen-MoE) report
steady-state all-to-all dispatch+combine overhead in the 10-25% band on
decode tokens, depending on whether expert-parallelism stays intra-node.
These numbers are not in the calibration table (which is Llama-3-70B dense),
so we apply them on top of calibrated decode tps.
"""

# Penalty fractions in [0, 1] applied to aggregate decode tps.
MOE_ROUTING_OVERHEAD_SINGLE_GPU = 0.0    # no all-to-all when EP=1
MOE_ROUTING_OVERHEAD_INTRA_NODE = 0.12   # NVLink/IF intra-node — observed ~10-15%
MOE_ROUTING_OVERHEAD_MULTI_NODE = 0.22   # IB cross-node — observed ~20-25%


def routing_overhead(num_experts: int, active_experts: int, nodes: int, gpu_count: int) -> float:
    """Return the all-to-all dispatch+combine penalty as a fraction in [0, 1].

    Returns 0.0 when no routing is needed (EP=1, dense, or all experts active).
    """
    if num_experts <= 1 or active_experts >= num_experts:
        return 0.0
    if gpu_count <= 1:
        return MOE_ROUTING_OVERHEAD_SINGLE_GPU
    if nodes > 1:
        return MOE_ROUTING_OVERHEAD_MULTI_NODE
    return MOE_ROUTING_OVERHEAD_INTRA_NODE
