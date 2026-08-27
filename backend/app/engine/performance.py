"""Performance calculation engine — Roofline model, tokens/sec, KV cache sizing."""

from dataclasses import dataclass

PRECISION_BYTES = {
    "FP4": 0.5,
    "FP8": 1.0,
    "FP16": 2.0,
    "BF16": 2.0,
    "FP32": 4.0,
}

# Fixed latency per tensor-parallel collective (all-reduce), in seconds.
# Small-message NCCL/RCCL all-reduces over NVLink/Infinity Fabric are
# latency-bound, not bandwidth-bound — the actual bytes moved per collective
# (a batch's worth of activations for one layer) are tiny relative to
# 900 GB/s-class interconnects, so kernel-launch + synchronization latency
# dominates, not transfer time. ~15us is the commonly cited ballpark for an
# intra-node NVLink4/5 all-reduce. A standard TP transformer layer issues 2
# collectives (post-attention, post-MLP), so this cost scales with
# num_layers and is negligible at low gpu_count but adds up at high TP
# degree — exactly the regime (8-way TP for a small-active-param MoE model)
# where real serving throughput was measured well below the pure roofline
# estimate. See validate_real_world_benchmarks.py.
TP_COLLECTIVE_LATENCY_S = 15e-6
TP_COLLECTIVES_PER_LAYER = 2

# Effective HBM bandwidth for reading the KV cache, relative to the
# contiguous bandwidth used for streaming model weights. Real serving
# engines store the KV cache in fixed-size non-contiguous blocks (vLLM
# PagedAttention, TRT-LLM paged KV) to avoid fragmentation — this trades
# some effective bandwidth for that flexibility, via smaller transaction
# sizes and pointer-chasing across blocks. ~50% is a conservative estimate;
# it only affects long-context decode (the KV-read term is negligible vs.
# model weights at short context, so this has ~no effect there).
KV_READ_BW_EFFICIENCY = 0.5


def _tp_comm_latency_s(gpu_count: int, num_layers: int | None) -> float:
    """Fixed per-token latency from tensor-parallel collectives (seconds)."""
    if gpu_count <= 1 or not num_layers:
        return 0.0
    return num_layers * TP_COLLECTIVES_PER_LAYER * TP_COLLECTIVE_LATENCY_S

# Architecture shapes for representative production LLMs, keyed by total
# parameter count in billions. ``get_model_arch`` matches by closest key.
# Keys correspond to real shipping models:
#   7   — Llama-3-8B / Mistral-7B class (GQA, 8 KV heads)
#   13  — Llama-2-13B (MHA, 40 KV heads — older architecture, kept for legacy sizing)
#   22  — Mixtral-8x22B *active* params (MoE backbone shape used for KV)
#   24  — Mistral-Small-3 / Mistral-Small-3.1 (24B dense)
#   27  — Gemma-2-27B (16 KV heads)
#   32  — Qwen2.5-32B (replaces synthetic 34B)
#   70  — Llama-3.1-70B / Qwen2.5-72B (8 KV heads, GQA)
#   405 — Llama-3.1-405B (8 KV heads, GQA)
#   671 — DeepSeek-V3 *total* params (MoE; KV uses MLA — 128 KV heads is an
#         approximation since MLA's compressed-rank cache doesn't fit this schema)
#   1500— Hypothetical frontier-scale model
MODEL_ARCHITECTURES = {
    7: {"num_layers": 32, "hidden_dim": 4096, "num_heads": 32, "num_kv_heads": 8, "head_dim": 128},
    13: {"num_layers": 40, "hidden_dim": 5120, "num_heads": 40, "num_kv_heads": 40, "head_dim": 128},  # Llama-2-13B (MHA)
    22: {"num_layers": 56, "hidden_dim": 6144, "num_heads": 48, "num_kv_heads": 8, "head_dim": 128},   # Mixtral-8x22B active
    24: {"num_layers": 40, "hidden_dim": 5120, "num_heads": 32, "num_kv_heads": 8, "head_dim": 128},   # Mistral-Small-3
    27: {"num_layers": 46, "hidden_dim": 4608, "num_heads": 32, "num_kv_heads": 16, "head_dim": 128},  # Gemma-2-27B
    32: {"num_layers": 64, "hidden_dim": 5120, "num_heads": 40, "num_kv_heads": 8, "head_dim": 128},   # Qwen2.5-32B
    70: {"num_layers": 80, "hidden_dim": 8192, "num_heads": 64, "num_kv_heads": 8, "head_dim": 128},
    405: {"num_layers": 126, "hidden_dim": 16384, "num_heads": 128, "num_kv_heads": 8, "head_dim": 128},
    671: {"num_layers": 61, "hidden_dim": 7168, "num_heads": 128, "num_kv_heads": 128, "head_dim": 128},  # DeepSeek-V3 (MLA approx)
    1500: {"num_layers": 160, "hidden_dim": 24576, "num_heads": 192, "num_kv_heads": 24, "head_dim": 128},
}


@dataclass
class PerformanceResult:
    prefill_tokens_per_sec: float
    decode_tokens_per_sec: float
    kv_cache_gb: float
    max_context_tokens: int
    model_memory_gb: float
    total_memory_required_gb: float
    is_compute_bound_prefill: bool
    is_memory_bw_bound_decode: bool


def get_model_arch(params_b: float) -> dict:
    """Get closest model architecture for a given param count."""
    sizes = sorted(MODEL_ARCHITECTURES.keys())
    closest = min(sizes, key=lambda s: abs(s - params_b))
    arch = MODEL_ARCHITECTURES[closest].copy()
    # Scale layers proportionally for non-standard sizes
    if abs(closest - params_b) > 5:
        scale = params_b / closest
        arch["num_layers"] = max(1, int(arch["num_layers"] * scale))
    return arch


def calc_model_memory_gb(params_b: float, precision: str) -> float:
    """Memory required to store model weights."""
    bytes_per_param = PRECISION_BYTES.get(precision, 2.0)
    return params_b * bytes_per_param


def calc_kv_cache_gb(
    num_layers: int,
    hidden_dim: int,
    context_length: int,
    batch_size: int,
    precision: str,
    num_kv_heads: int | None = None,
    head_dim: int = 128,
) -> float:
    """KV cache memory: 2 * num_layers * kv_dim * context_len * precision_bytes * batch_size.

    Uses GQA-aware kv_dim (num_kv_heads * head_dim) when available,
    falling back to hidden_dim for MHA models.

    .. deprecated:: Prefer ``calc_kv_cache_per_user_gb`` for per-user sizing
       inside ``calculate_performance``.  Kept for backward compatibility.
    """
    bytes_per_elem = PRECISION_BYTES.get(precision, 2.0)
    kv_dim = (num_kv_heads * head_dim) if num_kv_heads else hidden_dim
    kv_bytes = 2 * num_layers * kv_dim * context_length * bytes_per_elem * batch_size
    return kv_bytes / (1024**3)


def calc_prefill_tokens_per_sec(
    bf16_tflops: float,
    params_b: float,
    precision: str,
    mem_bandwidth_tb_s: float,
    *,
    context_length: int | None = None,
    num_layers: int | None = None,
    hidden_dim: int | None = None,
    batch_size: int = 1,
    gpu_count: int = 1,
) -> tuple[float, bool]:
    """Prefill throughput estimate (tokens/sec).

    Two-term FLOPs model when ``context_length`` is provided:
      - 2N forward-pass cost per token (Kaplan/Chinchilla)
      - O(L) per-token attention cost from the softmax(QK^T)V step,
        which scales with ``num_layers × hidden_dim × context_length``.
        At long context (>32K) this term dominates the FFN cost.

    Without context_length / arch, falls back to the 2N-only model — accurate
    for short prompts, optimistic for long ones.

    ``batch_size`` is the number of prompts being prefilled concurrently
    (continuous batching). The GPU's compute/bandwidth pool is fixed, so
    ``batch_size`` concurrent prefills divide it between them — per-request
    throughput drops roughly proportionally to how many share the GPU at
    once. This is a coarse model: it doesn't capture request queueing under
    saturating load, so it still overstates real per-request throughput at
    high concurrency (validated against real vLLM serving data — see
    ``validate_real_world_benchmarks.py``).

    ``gpu_count`` > 1 adds a fixed per-token tensor-parallel communication
    latency (see ``_tp_comm_latency_s``) — real, not fitted, and only
    material at high TP degree / many layers.
    """
    bytes_per_param = PRECISION_BYTES.get(precision, 2.0)
    effective_tflops = bf16_tflops
    if precision == "FP8":
        effective_tflops = bf16_tflops * 2.0  # FP8 tensor cores ~2x BF16
    elif precision == "FP4":
        effective_tflops = bf16_tflops * 4.0

    # FFN + projections: ~2N FLOPs per token (forward pass)
    flops_per_token = 2 * params_b * 1e9

    # Attention: per-token cost grows linearly with context length.
    # Per layer: Q×K^T + Softmax×V each cost L × hidden_dim FLOPs per token.
    # Total across all layers: ~2 × num_layers × hidden_dim × L per token.
    if context_length and num_layers and hidden_dim:
        attention_flops_per_token = 2 * num_layers * hidden_dim * context_length
        flops_per_token += attention_flops_per_token

    compute_limit = (effective_tflops * 1e12) / flops_per_token

    # Memory bandwidth limit. Weights are streamed once per prompt (not per
    # token), so the per-token mem cost is (model_bytes / L). Without a
    # context length, fall back to per-token = model_bytes (decode-like) which
    # under-estimates prefill but preserves legacy callers' expectations.
    model_bytes = params_b * 1e9 * bytes_per_param
    if context_length:
        mem_limit = (mem_bandwidth_tb_s * 1e12) * context_length / model_bytes
    else:
        mem_limit = (mem_bandwidth_tb_s * 1e12) / model_bytes

    is_compute_bound = compute_limit < mem_limit
    tokens_per_sec = min(compute_limit, mem_limit) / max(1, batch_size)

    # Unlike decode (one set of collectives per output token), prefill runs
    # the whole prompt through in one forward pass — the collectives happen
    # ONCE per request, not once per token, so the fixed comm latency is
    # amortized across every token in the prompt (negligible unless prompts
    # are very short).
    comm_latency_s = _tp_comm_latency_s(gpu_count, num_layers)
    if comm_latency_s > 0 and tokens_per_sec > 0:
        comm_latency_per_token_s = comm_latency_s / max(1, context_length or 1)
        tokens_per_sec = 1.0 / ((1.0 / tokens_per_sec) + comm_latency_per_token_s)

    return tokens_per_sec, is_compute_bound


def calc_decode_tokens_per_sec(
    mem_bandwidth_tb_s: float,
    params_b: float,
    precision: str,
    *,
    context_length: int | None = None,
    num_layers: int | None = None,
    kv_dim: int | None = None,
    batch_size: int = 1,
    gpu_count: int = 1,
) -> float:
    """Decode throughput estimate (tokens/sec), per concurrent sequence.

    Memory-bandwidth bound: every decode step reads the model weights ONCE
    (continuous batching shares that read across every sequence in the step)
    but reads EACH sequence's own KV cache from HBM. For ``batch_size``
    concurrent sequences at the same context length:

      per-sequence tok/s = BW / (model_bytes + batch_size × L × per_token_kv_bytes / KV_READ_BW_EFFICIENCY)

    The KV-read term is small at short context/low concurrency but dominates
    at long context or high concurrency, which is when real serving throughput
    collapses well below the single-stream (``batch_size=1``) estimate —
    validated against real vLLM serving data, see
    ``validate_real_world_benchmarks.py``. The KV term is further discounted
    by ``KV_READ_BW_EFFICIENCY`` since paged/blocked KV-cache reads don't
    achieve the same effective bandwidth as the contiguous weight read.
    Without ``context_length``, falls back to model-only — accurate for
    short context, optimistic above ~32K or at high concurrency.

    ``gpu_count`` > 1 adds a fixed per-token tensor-parallel communication
    latency (see ``_tp_comm_latency_s``).
    """
    bytes_per_param = PRECISION_BYTES.get(precision, 2.0)
    model_bytes = params_b * 1e9 * bytes_per_param

    bytes_per_token = model_bytes
    if context_length and num_layers and kv_dim:
        # Per-token KV-cache bytes: 2 (K+V) × layers × kv_dim × bytes_per_elem.
        # Total KV streamed per output token: L × per-token-bytes, read once
        # per concurrent sequence sharing this decode step. Divided by
        # KV_READ_BW_EFFICIENCY to reflect paged/non-contiguous KV access
        # achieving less than the weight-read's contiguous bandwidth.
        kv_bytes_per_pos = 2 * num_layers * kv_dim * bytes_per_param
        bytes_per_token += (
            max(1, batch_size) * context_length * kv_bytes_per_pos / KV_READ_BW_EFFICIENCY
        )

    tokens_per_sec = (mem_bandwidth_tb_s * 1e12) / bytes_per_token

    comm_latency_s = _tp_comm_latency_s(gpu_count, num_layers)
    if comm_latency_s > 0 and tokens_per_sec > 0:
        tokens_per_sec = 1.0 / ((1.0 / tokens_per_sec) + comm_latency_s)

    return tokens_per_sec


def calc_concurrent_users_support(
    memory_gb: float,
    model_params_b: float,
    precision: str,
    context_length: int,
    kv_cache_per_user_gb: float | None = None,
) -> int:
    """Calculate how many concurrent users can be supported based on VRAM.

    - Determine Weight Footprint from precision
    - Calculate Headroom: Available_KV_VRAM = GPU_Memory_GB - Weight_Footprint_GB
    - Calculate Users: Divide Available_KV_VRAM by per-user KV cache

    When kv_cache_per_user_gb is None, it is computed dynamically from
    context_length, precision, and model architecture (GQA-aware).
    """
    # Weight footprint calculation
    weight_footprint_gb = calc_model_memory_gb(model_params_b, precision)

    # Available VRAM for KV cache
    available_kv_vram = memory_gb - weight_footprint_gb

    if available_kv_vram <= 0:
        return 0

    # Compute per-user KV cache dynamically if not provided
    if kv_cache_per_user_gb is None:
        kv_cache_per_user_gb = calc_kv_cache_per_user_gb(context_length, precision, model_params_b)

    if kv_cache_per_user_gb <= 0:
        return 0

    concurrent_users = int(available_kv_vram / kv_cache_per_user_gb)
    return max(0, concurrent_users)


def calc_kv_cache_per_user_gb(
    context_length: int,
    precision: str,
    params_b: float,
) -> float:
    """Calculate KV cache memory per user based on context length and model size.

    Uses GQA-aware KV dimension (num_kv_heads * head_dim) for accurate sizing.
    For 70B Llama 3 FP8 @ 4K context this yields ~0.6 GB/user, matching
    industry benchmarks.
    """
    arch = get_model_arch(params_b)
    bytes_per_elem = PRECISION_BYTES.get(precision, 2.0)
    kv_dim = arch.get("num_kv_heads", arch["num_heads"]) * arch["head_dim"]

    # KV cache per sequence: 2 * num_layers * kv_dim * context_length * bytes_per_elem
    kv_bytes_per_sequence = 2 * arch["num_layers"] * kv_dim * context_length * bytes_per_elem
    kv_gb_per_sequence = kv_bytes_per_sequence / (1024**3)

    return kv_gb_per_sequence


def calc_max_context_tokens(
    hbm_capacity_gb: float,
    model_memory_gb: float,
    num_layers: int,
    hidden_dim: int,
    precision: str,
    gpu_count: int = 1,
    num_kv_heads: int | None = None,
    head_dim: int = 128,
) -> int:
    """Max context length that fits in VRAM after model weights.

    Uses GQA-aware kv_dim when num_kv_heads is provided.
    """
    total_hbm = hbm_capacity_gb * gpu_count
    remaining_gb = total_hbm - model_memory_gb
    if remaining_gb <= 0:
        return 0
    bytes_per_elem = PRECISION_BYTES.get(precision, 2.0)
    kv_dim = (num_kv_heads * head_dim) if num_kv_heads else hidden_dim
    # KV cache per token = 2 * num_layers * kv_dim * bytes_per_elem
    bytes_per_token = 2 * num_layers * kv_dim * bytes_per_elem
    max_tokens = int((remaining_gb * 1024**3) / bytes_per_token)
    return max(0, max_tokens)


def calculate_performance(
    params_b: float,
    precision: str,
    context_length: int,
    batch_size: int,
    bf16_tflops: float,
    mem_bandwidth_tb_s: float,
    hbm_capacity_gb: float,
    gpu_count: int = 1,
    is_moe: bool = False,
    num_experts: int = 8,
    active_experts: int = 2,
    # New fields for Phase 4
    memory_gb: float = None,
    memory_type: str = None,
    interconnect_type: str = None,
    supports_fp4: bool = None,
) -> PerformanceResult:
    """Full performance calculation for a given GPU config.

    Phase 4 Updates:
    - Use new memory_gb field if available, fallback to hbm_capacity_gb
    - Adjust calculations for PCIe vs NVLink interconnects
    - Implement proper concurrent user support calculations

    For MoE models: memory sizing uses full params (all experts stored in VRAM),
    but compute/bandwidth per token uses only the active fraction.
    """
    # Use new memory field if available, otherwise fallback
    effective_memory_gb = memory_gb if memory_gb is not None else hbm_capacity_gb
    
    # PCIe GPUs (e.g. RTX PRO 6000 BSE) operate as independent instances
    # (tp_degree=1, dp scaling only) so local memory bandwidth is unaffected.
    effective_bandwidth_tb_s = mem_bandwidth_tb_s

    arch = get_model_arch(params_b)

    # Memory: all experts must be stored in VRAM
    model_mem = calc_model_memory_gb(params_b, precision)

    # For MoE models, KV cache depends on the base/backbone architecture,
    # not total expert-inflated params.  E.g. Mixtral 8×22B has 176B total
    # params but KV cache matches a ~22B dense model.
    kv_params_b = params_b
    if is_moe and num_experts > 0:
        kv_params_b = params_b / num_experts  # approximate backbone size

    # KV cache calculation with proper concurrent user support (GQA-aware)
    kv_per_user = calc_kv_cache_per_user_gb(context_length, precision, kv_params_b)
    kv_cache = kv_per_user * batch_size

    total_mem = model_mem + kv_cache

    # Compute/bandwidth: MoE only activates a fraction of params per token
    active_params_b = params_b
    if is_moe and num_experts > 0:
        active_params_b = params_b * (active_experts / num_experts)

    # Determine effective precision — if GPU doesn't support FP4, fall back to FP8
    effective_precision = precision
    if precision == "FP4" and not supports_fp4:
        effective_precision = "FP8"

    # TFLOPS scaling for precision is handled inside calc_prefill_tokens_per_sec.
    # Pass arch + context so the long-context attention (prefill) and KV-read
    # (decode) terms are included.
    kv_dim = arch.get("num_kv_heads", arch["num_heads"]) * arch["head_dim"]
    # batch_size here is the concurrent-sequence count sharing this GPU
    # group's compute/bandwidth pool (see calc_decode_tokens_per_sec /
    # calc_prefill_tokens_per_sec) — the same value already used above to
    # size the KV cache for all concurrent sequences.
    prefill_tps, is_compute_bound = calc_prefill_tokens_per_sec(
        bf16_tflops * gpu_count, active_params_b, effective_precision,
        effective_bandwidth_tb_s * gpu_count,
        context_length=context_length,
        num_layers=arch["num_layers"],
        hidden_dim=arch["hidden_dim"],
        batch_size=batch_size,
        gpu_count=gpu_count,
    )
    decode_tps = calc_decode_tokens_per_sec(
        effective_bandwidth_tb_s * gpu_count, active_params_b, effective_precision,
        context_length=context_length,
        num_layers=arch["num_layers"],
        kv_dim=kv_dim,
        batch_size=batch_size,
        gpu_count=gpu_count,
    )

    max_ctx = calc_max_context_tokens(
        effective_memory_gb, model_mem, arch["num_layers"], arch["hidden_dim"], precision, gpu_count,
        num_kv_heads=arch.get("num_kv_heads"), head_dim=arch["head_dim"],
    )

    return PerformanceResult(
        prefill_tokens_per_sec=prefill_tps,
        decode_tokens_per_sec=decode_tps,
        kv_cache_gb=kv_cache,
        max_context_tokens=max_ctx,
        model_memory_gb=model_mem,
        total_memory_required_gb=total_mem,
        is_compute_bound_prefill=is_compute_bound,
        is_memory_bw_bound_decode=True,
    )


@dataclass
class InteractiveCeilingResult:
    memory_ceiling: int    # max concurrent sequences the VRAM can hold
    latency_ceiling: int   # max concurrent sequences that stay under the SLA
    ceiling: int           # min(memory_ceiling, latency_ceiling) — the real answer
    binding_constraint: str  # "memory" or "latency" (whichever is smaller)


def calc_interactive_ceiling(
    memory_gb: float,
    params_b: float,
    precision: str,
    context_length: int,
    bf16_tflops: float,
    mem_bandwidth_tb_s: float,
    *,
    gpu_count: int = 1,
    ttft_sla_s: float = 1.5,
    min_decode_tps_per_user: float = 5.0,
) -> InteractiveCeilingResult:
    """How many concurrent interactive sessions a GPU (group) can actually serve.

    ``calc_concurrent_users_support`` answers "how many sessions' KV caches
    fit in VRAM" — a pure capacity bound with no notion of latency. In
    practice, real serving hits a latency SLA well before VRAM runs out:
    real vLLM benchmarks (see validate_real_world_benchmarks.py) show the
    "interactive ceiling" — sessions that stay under a P99 TTFT bound — is
    routinely 4-6x lower than the memory-only estimate at short context.

    This finds the largest ``batch_size`` (concurrent sessions) for which,
    using the batch/TP-aware roofline above:
      - prefill latency (context_length / prefill_tps) stays under ``ttft_sla_s``
      - decode throughput per session stays at or above ``min_decode_tps_per_user``

    and returns the smaller of that latency ceiling and the memory ceiling.
    Uncalibrated (raw roofline), matching ``calc_concurrent_users_support``'s
    own convention — callers wanting calibrated numbers should calibrate the
    decode/prefill throughput before/after, not this ceiling directly.
    """
    memory_ceiling = calc_concurrent_users_support(memory_gb, params_b, precision, context_length)

    if memory_ceiling <= 0:
        return InteractiveCeilingResult(0, 0, 0, "memory")

    arch = get_model_arch(params_b)
    kv_dim = arch.get("num_kv_heads", arch["num_heads"]) * arch["head_dim"]

    def meets_sla(n: int) -> bool:
        prefill_tps, _ = calc_prefill_tokens_per_sec(
            bf16_tflops * gpu_count, params_b, precision, mem_bandwidth_tb_s * gpu_count,
            context_length=context_length, num_layers=arch["num_layers"], hidden_dim=arch["hidden_dim"],
            batch_size=n, gpu_count=gpu_count,
        )
        decode_tps = calc_decode_tokens_per_sec(
            mem_bandwidth_tb_s * gpu_count, params_b, precision,
            context_length=context_length, num_layers=arch["num_layers"], kv_dim=kv_dim,
            batch_size=n, gpu_count=gpu_count,
        )
        ttft_s = (context_length / prefill_tps) if prefill_tps > 0 else float("inf")
        return ttft_s <= ttft_sla_s and decode_tps >= min_decode_tps_per_user

    # Both latency terms degrade monotonically with n, so the SLA is met on a
    # contiguous [1, k] prefix — binary search for the boundary k.
    if not meets_sla(1):
        latency_ceiling = 0
    else:
        lo, hi = 1, memory_ceiling
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if meets_sla(mid):
                lo = mid
            else:
                hi = mid - 1
        latency_ceiling = lo

    ceiling = min(memory_ceiling, latency_ceiling)
    binding = "latency" if latency_ceiling <= memory_ceiling else "memory"
    return InteractiveCeilingResult(memory_ceiling, latency_ceiling, ceiling, binding)
