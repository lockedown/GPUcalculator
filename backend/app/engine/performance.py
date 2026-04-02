"""Performance calculation engine — Roofline model, tokens/sec, KV cache sizing."""

from dataclasses import dataclass

PRECISION_BYTES = {
    "FP4": 0.5,
    "FP8": 1.0,
    "FP16": 2.0,
    "BF16": 2.0,
    "FP32": 4.0,
}

# Approximate model architecture params for common LLMs
MODEL_ARCHITECTURES = {
    7: {"num_layers": 32, "hidden_dim": 4096, "num_heads": 32, "head_dim": 128},
    13: {"num_layers": 40, "hidden_dim": 5120, "num_heads": 40, "head_dim": 128},
    34: {"num_layers": 48, "hidden_dim": 8192, "num_heads": 64, "head_dim": 128},
    70: {"num_layers": 80, "hidden_dim": 8192, "num_heads": 64, "head_dim": 128},
    405: {"num_layers": 126, "hidden_dim": 16384, "num_heads": 128, "head_dim": 128},
    1500: {"num_layers": 160, "hidden_dim": 24576, "num_heads": 192, "head_dim": 128},
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
) -> float:
    """KV cache memory: 2 * num_layers * hidden_dim * context_len * precision_bytes * batch_size."""
    bytes_per_elem = PRECISION_BYTES.get(precision, 2.0)
    kv_bytes = 2 * num_layers * hidden_dim * context_length * bytes_per_elem * batch_size
    return kv_bytes / (1024**3)


def calc_prefill_tokens_per_sec(
    bf16_tflops: float,
    params_b: float,
    precision: str,
    mem_bandwidth_tb_s: float,
) -> tuple[float, bool]:
    """
    Prefill is compute-bound when arithmetic intensity is high.
    tokens/sec = FLOPS / (2 * params * bytes_per_param)
    Also check roofline: compare compute vs memory bandwidth limit.
    """
    bytes_per_param = PRECISION_BYTES.get(precision, 2.0)
    # Use precision-appropriate TFLOPS (approximate scaling)
    effective_tflops = bf16_tflops
    if precision == "FP8":
        effective_tflops = bf16_tflops * 2.0  # FP8 tensor cores ~2x BF16
    elif precision == "FP4":
        effective_tflops = bf16_tflops * 4.0

    flops_per_token = 2 * params_b * 1e9  # ~2N FLOPs per token (forward pass)
    compute_limit = (effective_tflops * 1e12) / flops_per_token

    # Memory bandwidth limit for prefill (loading weights once per batch)
    model_bytes = params_b * 1e9 * bytes_per_param
    mem_limit = (mem_bandwidth_tb_s * 1e12) / model_bytes

    is_compute_bound = compute_limit < mem_limit
    tokens_per_sec = min(compute_limit, mem_limit)

    return tokens_per_sec, is_compute_bound


def calc_decode_tokens_per_sec(
    mem_bandwidth_tb_s: float,
    params_b: float,
    precision: str,
) -> float:
    """
    Decode is memory-bandwidth-bound (autoregressive, 1 token at a time per sequence).
    tokens/sec = mem_bandwidth / (params * bytes_per_param)
    """
    bytes_per_param = PRECISION_BYTES.get(precision, 2.0)
    model_bytes = params_b * 1e9 * bytes_per_param
    tokens_per_sec = (mem_bandwidth_tb_s * 1e12) / model_bytes
    return tokens_per_sec


def calc_max_context_tokens(
    hbm_capacity_gb: float,
    model_memory_gb: float,
    num_layers: int,
    hidden_dim: int,
    precision: str,
    gpu_count: int = 1,
) -> int:
    """Max context length that fits in VRAM after model weights."""
    total_hbm = hbm_capacity_gb * gpu_count
    remaining_gb = total_hbm - model_memory_gb
    if remaining_gb <= 0:
        return 0
    bytes_per_elem = PRECISION_BYTES.get(precision, 2.0)
    # KV cache per token = 2 * num_layers * hidden_dim * bytes_per_elem
    bytes_per_token = 2 * num_layers * hidden_dim * bytes_per_elem
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
) -> PerformanceResult:
    """Full performance calculation for a given GPU config."""
    arch = get_model_arch(params_b)

    model_mem = calc_model_memory_gb(params_b, precision)
    kv_cache = calc_kv_cache_gb(
        arch["num_layers"], arch["hidden_dim"], context_length, batch_size, precision
    )
    total_mem = model_mem + kv_cache

    prefill_tps, is_compute_bound = calc_prefill_tokens_per_sec(
        bf16_tflops * gpu_count, params_b, precision, mem_bandwidth_tb_s * gpu_count
    )
    decode_tps = calc_decode_tokens_per_sec(
        mem_bandwidth_tb_s * gpu_count, params_b, precision
    )

    max_ctx = calc_max_context_tokens(
        hbm_capacity_gb, model_mem, arch["num_layers"], arch["hidden_dim"], precision, gpu_count
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
