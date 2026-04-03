"""Calibration layer — adjusts roofline estimates to match HTML benchmark ground truth.

The HTML tokenization benchmarks provide real/estimated decode and prefill numbers
for Llama3-70B at FP16.  We derive per-GPU calibration multipliers so the engine
reproduces those figures within ±15%.

Reference values (from `Finance GPU Benchmark Matrix.html`, Llama3-70B FP16):
  GPU               Decode (tok/s)   Prefill (K tok/s)
  H200 SXM5              55              20
  B100 SXM               90              32
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
    "B100 HGX": 90.0,
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
    "B100 HGX": 32_000.0,
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
    "B100 HGX": 1.8,
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

    Values must match seed.py / HTML source data.
    """
    return {
        "H100 SXM5":          {"mem_bw": 3.35, "bf16": 1750},
        "H200 SXM":           {"mem_bw": 4.8,  "bf16": 1970},
        "B100 HGX":           {"mem_bw": 8.0,  "bf16": 1750},
        "B200 HGX":           {"mem_bw": 8.0,  "bf16": 2250},
        "B300 HGX":           {"mem_bw": 8.0,  "bf16": 2250},
        "GB200 NVL72":        {"mem_bw": 8.0,  "bf16": 2250},
        "GB300 NVL72":        {"mem_bw": 8.0,  "bf16": 2250},
        "RTX PRO 6000 BSE":   {"mem_bw": 1.6,  "bf16": 480},
        "MI300X":             {"mem_bw": 3.2,  "bf16": 1300},
        "MI350X":             {"mem_bw": 6.0,  "bf16": 1800},
        "MI355X":             {"mem_bw": 6.4,  "bf16": 2000},
    }


def get_decode_factor(gpu_name: str) -> float:
    """Calibration factor for decode tok/s (Llama3-70B FP16, batch=1)."""
    global _decode_factors
    if _decode_factors is None:
        from app.engine.performance import calc_decode_tokens_per_sec
        specs = _gpu_specs()
        _decode_factors = {}
        for name, ref in REFERENCE_DECODE.items():
            s = specs.get(name)
            if s:
                # For NVL72 rack-scale, reference is per-rack (72 GPUs aggregate)
                gpu_count = 72 if "NVL72" in name else 1
                raw = calc_decode_tokens_per_sec(s["mem_bw"] * gpu_count, 70, "FP16")
                _decode_factors[name] = ref / raw if raw > 0 else 1.0
            else:
                _decode_factors[name] = 1.0
    return _decode_factors.get(gpu_name, 1.0)


def get_prefill_factor(gpu_name: str) -> float:
    """Calibration factor for prefill tok/s (Llama3-70B FP16)."""
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
                    s["bf16"] * gpu_count, 70, "FP16", s["mem_bw"] * gpu_count
                )
                _prefill_factors[name] = ref / raw if raw > 0 else 1.0
            else:
                _prefill_factors[name] = 1.0
    return _prefill_factors.get(gpu_name, 1.0)


def get_fp8_multiplier(gpu_name: str) -> float:
    """FP8-over-FP16 throughput multiplier from benchmark data."""
    return FP8_MULTIPLIER.get(gpu_name, 1.0)


def calibrate_decode(gpu_name: str, raw_tps: float, precision: str) -> float:
    """Apply calibration + FP8 multiplier to raw decode tokens/sec."""
    calibrated = raw_tps * get_decode_factor(gpu_name)
    if precision in ("FP8", "FP4"):
        calibrated *= get_fp8_multiplier(gpu_name)
    return calibrated


def calibrate_prefill(gpu_name: str, raw_tps: float, precision: str) -> float:
    """Apply calibration + FP8 multiplier to raw prefill tokens/sec."""
    calibrated = raw_tps * get_prefill_factor(gpu_name)
    if precision in ("FP8", "FP4"):
        calibrated *= get_fp8_multiplier(gpu_name)
    return calibrated
