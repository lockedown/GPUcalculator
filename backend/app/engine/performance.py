"""Performance calculation engine — Roofline model, tokens/sec, KV cache sizing."""

from dataclasses import dataclass

PRECISION_BYTES = {
    "FP4": 0.5,
    "FP8": 1.0,
    "FP16": 2.0,
    "BF16": 2.0,
    "FP32": 4.0,
}

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
) -> tuple[float, bool]:
    """Prefill throughput estimate (tokens/sec).

    Two-term FLOPs model when ``context_length`` is provided:
      - 2N forward-pass cost per token (Kaplan/Chinchilla)
      - O(L) per-token attention cost from the softmax(QK^T)V step,
        which scales with ``num_layers × hidden_dim × context_length``.
        At long context (>32K) this term dominates the FFN cost.

    Without context_length / arch, falls back to the 2N-only model — accurate
    for short prompts, optimistic for long ones.
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
    tokens_per_sec = min(compute_limit, mem_limit)

    return tokens_per_sec, is_compute_bound


def calc_decode_tokens_per_sec(
    mem_bandwidth_tb_s: float,
    params_b: float,
    precision: str,
    *,
    context_length: int | None = None,
    num_layers: int | None = None,
    kv_dim: int | None = None,
) -> float:
    """Decode throughput estimate (tokens/sec).

    Memory-bandwidth bound: every output token requires streaming the model
    weights AND reading the full per-sequence KV cache from HBM.

      tok/s = BW / (model_bytes + L × per_token_kv_bytes)

    The KV-read term is small at short context (<5% at 4K for L3-70B) but
    dominates at long context (>30% at 128K). Without ``context_length``,
    falls back to model-only — accurate for short context, optimistic above ~32K.
    """
    bytes_per_param = PRECISION_BYTES.get(precision, 2.0)
    model_bytes = params_b * 1e9 * bytes_per_param

    bytes_per_token = model_bytes
    if context_length and num_layers and kv_dim:
        # Per-token KV-cache bytes: 2 (K+V) × layers × kv_dim × bytes_per_elem.
        # Total KV streamed per output token: L × per-token-bytes.
        kv_bytes_per_pos = 2 * num_layers * kv_dim * bytes_per_param
        bytes_per_token += context_length * kv_bytes_per_pos

    tokens_per_sec = (mem_bandwidth_tb_s * 1e12) / bytes_per_token
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
    prefill_tps, is_compute_bound = calc_prefill_tokens_per_sec(
        bf16_tflops * gpu_count, active_params_b, effective_precision,
        effective_bandwidth_tb_s * gpu_count,
        context_length=context_length,
        num_layers=arch["num_layers"],
        hidden_dim=arch["hidden_dim"],
    )
    decode_tps = calc_decode_tokens_per_sec(
        effective_bandwidth_tb_s * gpu_count, active_params_b, effective_precision,
        context_length=context_length,
        num_layers=arch["num_layers"],
        kv_dim=kv_dim,
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
