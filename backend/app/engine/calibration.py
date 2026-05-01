"""Calibration layer — adjusts roofline estimates to match HTML benchmark ground truth.

The HTML tokenization benchmarks provide real/estimated decode and prefill numbers
for Llama3-70B at FP16.  We derive per-GPU calibration multipliers so the engine
reproduces those figures within ±15%.

Reference values (from `Finance GPU Benchmark Matrix.html`, Llama3-70B FP16):
  GPU               Decode (tok/s)   Prefill (K tok/s)
  H200 SXM5              55              20
  B200 SXM              115              45
  B300 SXM              170              70   (est.)
  GB200 NVL72           200              82   (rack)
  GB300 NVL72           280             130   (est.)
  MI300X                 70              22
  MI350X                100              38   (est.)
  MI355X                118              46   (est.)
"""

from __future__ import annotations

# Ground-truth decode tok/s for Llama3-70B FP16 (batch=1, single GPU / rack unit)
REFERENCE_DECODE: dict[str, float] = {
    "H100 SXM5": 40.0,
    "H200 SXM": 55.0,
    "B200 HGX": 115.0,
    "B300 HGX": 170.0,
    "GB200 NVL72": 200.0,
    "GB300 NVL72": 280.0,
    "RTX PRO 6000 BSE": 32.0,
    "MI300X": 70.0,
    "MI350X": 100.0,
    "MI355X": 118.0,
}

# Ground-truth prefill K tok/s for Llama3-70B FP16
REFERENCE_PREFILL: dict[str, float] = {
    "H100 SXM5": 14_000.0,
    "H200 SXM": 20_000.0,
    "B200 HGX": 45_000.0,
    "B300 HGX": 70_000.0,
    "GB200 NVL72": 82_000.0,
    "GB300 NVL72": 130_000.0,
    "RTX PRO 6000 BSE": 8_000.0,
    "MI300X": 22_000.0,
    "MI350X": 38_000.0,
    "MI355X": 46_000.0,
}

# FP8 multiplier over FP16 (from HTML "FP8 Quantised Throughput" row)
FP8_MULTIPLIER: dict[str, float] = {
    "H100 SXM5": 1.8,       # FP8 Transformer Engine on Hopper
    "H200 SXM": 1.8,        # Same Hopper compute die as H100
    "B200 HGX": 1.9,
    "B300 HGX": 2.1,
    "GB200 NVL72": 2.2,
    "GB300 NVL72": 2.4,
    "RTX PRO 6000 BSE": 2.0, # 5th-gen Tensor Cores, FP8/FP4
    "MI300X": 1.0,           # Partial / marginal
    "MI350X": 1.7,
    "MI355X": 1.8,
}


def _build_calibration_factors(
    roofline_fn,
    reference: dict[str, float],
) -> dict[str, float]:
    """Compute multiplier so that roofline_value * factor ≈ reference."""
    factors: dict[str, float] = {}
    for gpu_name, ref in reference.items():
        raw = roofline_fn(gpu_name)
        if raw and raw > 0:
            factors[gpu_name] = ref / raw
        else:
            factors[gpu_name] = 1.0
    return factors


# Lazy-init cache — built once on first access
_decode_factors: dict[str, float] | None = None
_prefill_factors: dict[str, float] | None = None


def _gpu_specs() -> dict[str, dict]:
    """Minimal GPU specs for roofline calculation (avoids DB dependency).

    BF16 figures are *dense* TFLOPS from NVIDIA / AMD datasheets, matching the
    HTML source ("989 BF16 TFLOPS" for Hopper, "2.25 PF BF16" for B200, etc.).
    Sparsity (2:4) is not used in real LLM inference, so do not mix sparse
    figures here — the calibration factor would silently absorb the difference
    and give wrong predictions for non-Llama3-70B workloads.
    """
    return {
        "H100 SXM5":          {"mem_bw": 3.35, "bf16": 989},
        "H200 SXM":           {"mem_bw": 4.8,  "bf16": 989},   # Same Hopper compute die
        "B200 HGX":           {"mem_bw": 8.0,  "bf16": 2250},
        "B300 HGX":           {"mem_bw": 8.0,  "bf16": 2800},  # Blackwell Ultra dense BF16 (est.)
        "GB200 NVL72":        {"mem_bw": 8.0,  "bf16": 2250},  # per-GPU
        "GB300 NVL72":        {"mem_bw": 8.0,  "bf16": 2800},  # per-GPU
        "RTX PRO 6000 BSE":   {"mem_bw": 1.6,  "bf16": 480},
        "MI300X":             {"mem_bw": 3.2,  "bf16": 1307},
        "MI350X":             {"mem_bw": 6.0,  "bf16": 1800},
        "MI355X":             {"mem_bw": 6.4,  "bf16": 2000},
    }


# Reference context length for the published Llama3-70B benchmarks the
# REFERENCE_DECODE / REFERENCE_PREFILL values were measured at. Calibration
# computes the raw roofline at this same context so the long-context KV-read
# (decode) and attention (prefill) terms stay consistent with the reference.
REFERENCE_CONTEXT_LENGTH = 4096

# Llama-3-70B architecture used inside calibration's roofline calls.
_LLAMA3_70B_ARCH = {"num_layers": 80, "hidden_dim": 8192, "num_kv_heads": 8, "head_dim": 128}


def get_decode_factor(gpu_name: str) -> float:
    """Calibration factor for decode tok/s (Llama3-70B FP16, 4K context, batch=1)."""
    global _decode_factors
    if _decode_factors is None:
        from app.engine.performance import calc_decode_tokens_per_sec
        specs = _gpu_specs()
        _decode_factors = {}
        kv_dim = _LLAMA3_70B_ARCH["num_kv_heads"] * _LLAMA3_70B_ARCH["head_dim"]
        for name, ref in REFERENCE_DECODE.items():
            s = specs.get(name)
            if s:
                # For NVL72 rack-scale, reference is per-rack (72 GPUs aggregate)
                gpu_count = 72 if "NVL72" in name else 1
                raw = calc_decode_tokens_per_sec(
                    s["mem_bw"] * gpu_count, 70, "FP16",
                    context_length=REFERENCE_CONTEXT_LENGTH,
                    num_layers=_LLAMA3_70B_ARCH["num_layers"],
                    kv_dim=kv_dim,
                )
                _decode_factors[name] = ref / raw if raw > 0 else 1.0
            else:
                _decode_factors[name] = 1.0
    return _decode_factors.get(gpu_name, 1.0)


def get_prefill_factor(gpu_name: str) -> float:
    """Calibration factor for prefill tok/s (Llama3-70B FP16, 4K context)."""
    global _prefill_factors
    if _prefill_factors is None:
        from app.engine.performance import calc_prefill_tokens_per_sec
        specs = _gpu_specs()
        _prefill_factors = {}
        for name, ref in REFERENCE_PREFILL.items():
            s = specs.get(name)
            if s:
                gpu_count = 72 if "NVL72" in name else 1
                raw, _ = calc_prefill_tokens_per_sec(
                    s["bf16"] * gpu_count, 70, "FP16", s["mem_bw"] * gpu_count,
                    context_length=REFERENCE_CONTEXT_LENGTH,
                    num_layers=_LLAMA3_70B_ARCH["num_layers"],
                    hidden_dim=_LLAMA3_70B_ARCH["hidden_dim"],
                )
                _prefill_factors[name] = ref / raw if raw > 0 else 1.0
            else:
                _prefill_factors[name] = 1.0
    return _prefill_factors.get(gpu_name, 1.0)


def get_fp8_multiplier(gpu_name: str) -> float:
    """FP8-over-FP16 throughput multiplier from benchmark data."""
    return FP8_MULTIPLIER.get(gpu_name, 1.0)


def _precision_residual(gpu_name: str, precision: str) -> float:
    """Residual correction for FP8/FP4 after the roofline already accounts for precision.

    ``performance.py`` already encodes the precision speed-up via bytes-per-param
    (decode, BW-bound) and TFLOPS multipliers (prefill, compute-bound) — FP8 ≈ 2×
    BF16, FP4 ≈ 4×. Multiplying by ``FP8_MULTIPLIER`` again would double-count.

    This function returns a *down-correction* only: when a GPU's measured FP8
    ratio is below the theoretical 2× (e.g. MI300X with partial FP8 support),
    we scale the throughput down accordingly. GPUs that meet or exceed the
    theoretical ratio get no further adjustment.
    """
    if precision == "FP8":
        theoretical = 2.0
    elif precision == "FP4":
        # No published FP4 ratio data; reuse FP8 ratio as a conservative proxy.
        theoretical = 4.0
    else:
        return 1.0
    measured = get_fp8_multiplier(gpu_name)
    if measured >= theoretical:
        return 1.0
    return measured / theoretical


def calibrate_decode(gpu_name: str, raw_tps: float, precision: str) -> float:
    """Apply calibration to raw decode tokens/sec.

    raw_tps already accounts for FP8/FP4 throughput gains via bytes-per-param
    in performance.py; we apply only the per-GPU calibration factor and a
    down-correction for hardware with weak low-precision support.
    """
    calibrated = raw_tps * get_decode_factor(gpu_name)
    return calibrated * _precision_residual(gpu_name, precision)


def calibrate_prefill(gpu_name: str, raw_tps: float, precision: str) -> float:
    """Apply calibration to raw prefill tokens/sec.

    raw_tps already accounts for FP8/FP4 TFLOPS gains in performance.py; we
    apply only the per-GPU calibration factor and a down-correction for
    hardware with weak low-precision support.
    """
    calibrated = raw_tps * get_prefill_factor(gpu_name)
    return calibrated * _precision_residual(gpu_name, precision)
