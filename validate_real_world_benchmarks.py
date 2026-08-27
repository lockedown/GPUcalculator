#!/usr/bin/env python3
"""
Validates the performance/calibration engine against real serving benchmarks.

Data source: HSBC_AIPG_GPU_Benchmark_Combined_Analysis.xlsx (WWT AI Proving
Ground, on-prem H200/MI300X nodes serving Qwen3.5-122B-A10B). This is real
measured vLLM serving data, not a synthetic/idle roofline test — so the
comparisons here are NOT a pass/fail against the engine's existing ±15%
calibration target (that target is against *idle single-stream* Llama3-70B
numbers). Instead this reports a measured/predicted ratio: how much of the
engine's idealized roofline throughput real contended serving actually
achieves, and how that ratio shifts with concurrency and context length.

Two sheets are used:

  "June 2026 (ATC open-loop)" — controlled concurrency sweep (4/16/64/128)
  at a FIXED 1,024-in / 512-out shape (see the sheet's own footer note).
  This is the cleanest comparison: same prompt/output shape, only GPU,
  precision, and concurrency vary. Engine calls: calc_prefill_tokens_per_sec
  (context_length=1024) and calc_decode_tokens_per_sec (context_length=
  midpoint of generation, ~1280).

  "July 2026 (O1 closed-loop)" / "Aug 2026 (O1 H200)" — the interactive-
  capacity sweep: for each context length, the max concurrent sessions
  that stay under a 1.5s TTFT SLA (the "interactive ceiling"), plus the
  decode/prefill latency measured AT that ceiling. Compared against the
  engine's calc_concurrent_users_support (pure VRAM/KV-capacity ceiling —
  it has no latency-SLA concept at all) and against idle-roofline decode/
  prefill.

Excluded on purpose (see the workbook's own caveats / quarantine notes):
  - Qwen3-Embedding-8B rows (not an autoregressive decode/prefill workload)
  - the RedHatAI DeepSeek-V4-Flash-BF16 rows (failed the workbook's own
    router-tensor integrity gate — not referenced by any formula in the
    workbook itself, so we don't reference them here either)
  - DeepSeek-V4-Flash generally (not in the engine's MODEL_ARCHITECTURES
    table and its true MoE shape isn't known here — out of scope for v1)

Usage:
    pip install -r requirements-dev.txt   # adds openpyxl on top of requirements.txt
    python validate_real_world_benchmarks.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.engine.performance import (  # noqa: E402
    get_model_arch,
    calc_decode_tokens_per_sec,
    calc_prefill_tokens_per_sec,
    calc_concurrent_users_support,
    calc_interactive_ceiling,
)
from app.engine.calibration import (  # noqa: E402
    calibrate_decode,
    calibrate_prefill,
    _gpu_specs,
)

try:
    import openpyxl
except ImportError:
    sys.exit("Missing dependency — run: pip install -r requirements-dev.txt")

XLSX_PATH = os.path.join(os.path.dirname(__file__), "HSBC_AIPG_GPU_Benchmark_Combined_Analysis.xlsx")

# Qwen3.5-122B-A10B: 122B total params, ~10B active per token (MoE — the
# "A10B" suffix is the active-param count). True expert count / backbone
# shape isn't public, so we reuse the engine's own Mixtral heuristic:
# approximate the attention/KV backbone as the active-param size.
MODEL_TOTAL_PARAMS_B = 122
MODEL_ACTIVE_PARAMS_B = 10

GPU_SPECS = _gpu_specs()  # {"H200 SXM": {"mem_bw": 4.8, "bf16": 989}, "MI300X": {...}, ...}


def norm_precision(raw: str) -> str:
    return "FP8" if "fp8" in raw.lower() else "BF16"


def norm_gpu(raw: str) -> str | None:
    raw = raw.lower()
    if "h200" in raw:
        return "H200 SXM"
    if "mi300x" in raw:
        return "MI300X"
    return None


def gpu_count_from_accelerator(raw: str) -> int:
    m = re.match(r"(\d+)x\s+", raw)
    return int(m.group(1)) if m else 1


def gpu_mem_gb_from_model_string(gpu_model: str) -> float | None:
    """Extract HBM capacity from strings like 'h200-141gb-sxm5' / 'mi300x-192gb-oam'."""
    m = re.search(r"(\d+)gb", gpu_model.lower())
    return float(m.group(1)) if m else None


def predict(gpu_name: str, precision: str, prefill_ctx: int, decode_ctx: int, gpu_count: int, batch_size: int = 1):
    specs = GPU_SPECS[gpu_name]
    arch = get_model_arch(MODEL_TOTAL_PARAMS_B)
    kv_dim = arch.get("num_kv_heads", arch["num_heads"]) * arch["head_dim"]

    decode_raw = calc_decode_tokens_per_sec(
        specs["mem_bw"] * gpu_count, MODEL_ACTIVE_PARAMS_B, precision,
        context_length=decode_ctx, num_layers=arch["num_layers"], kv_dim=kv_dim,
        batch_size=batch_size, gpu_count=gpu_count,
    )
    prefill_raw, _ = calc_prefill_tokens_per_sec(
        specs["bf16"] * gpu_count, MODEL_ACTIVE_PARAMS_B, precision,
        specs["mem_bw"] * gpu_count,
        context_length=prefill_ctx, num_layers=arch["num_layers"], hidden_dim=arch["hidden_dim"],
        batch_size=batch_size, gpu_count=gpu_count,
    )
    decode_cal = calibrate_decode(gpu_name, decode_raw, precision)
    prefill_cal = calibrate_prefill(gpu_name, prefill_raw, precision)
    return decode_raw, decode_cal, prefill_raw, prefill_cal


def ratio(measured: float, predicted: float) -> str:
    if not predicted:
        return "n/a"
    return f"{measured / predicted:5.2f}x"


def section(title: str):
    print(f"\n=== {title} ===")


def run_june_sheet(wb):
    section("June 2026 (ATC open-loop) — fixed 1,024-in/512-out, concurrency 4-128")
    print(f"{'gpu':<9} {'prec':<4} {'conc':>4} | {'decode measured':>15} {'raw':>8} {'calib':>8} {'m/calib':>8} "
          f"| {'prefill measured':>16} {'raw':>10} {'calib':>10} {'m/calib':>8}")

    ws = wb["June 2026 (ATC open-loop)"]
    ratios_decode, ratios_prefill = [], []
    for row in ws.iter_rows(min_row=2, values_only=True):
        accel, model = row[0], row[1]
        if not accel or not model:
            continue
        if "Qwen3.5-122B-A10B" not in model or "Embedding" in model:
            continue  # scope: flagship MoE model only (see module docstring)
        precision_raw, batch, output_tokens, ttft_ms, tpot_ms = row[3], row[5], row[6], row[7], row[8]
        if ttft_ms is None or tpot_ms is None:
            continue

        gpu_name = norm_gpu(accel)
        if not gpu_name:
            continue
        gpu_count = gpu_count_from_accelerator(accel)
        precision = norm_precision(precision_raw)

        prefill_ctx = 1024  # fixed input length per sheet footer note
        decode_ctx = prefill_ctx + output_tokens // 2  # midpoint of generation

        decode_raw, decode_cal, prefill_raw, prefill_cal = predict(
            gpu_name, precision, prefill_ctx, decode_ctx, gpu_count, batch_size=batch
        )
        measured_decode = 1000.0 / tpot_ms
        measured_prefill = prefill_ctx / (ttft_ms / 1000.0)

        ratios_decode.append(measured_decode / decode_cal)
        ratios_prefill.append(measured_prefill / prefill_cal)

        print(f"{gpu_name:<9} {precision:<4} {batch:>4} | "
              f"{measured_decode:>12.1f}tps {decode_raw:>8.1f} {decode_cal:>8.1f} {ratio(measured_decode, decode_cal):>8} | "
              f"{measured_prefill:>13.0f}tps {prefill_raw:>10.0f} {prefill_cal:>10.0f} {ratio(measured_prefill, prefill_cal):>8}")

    if ratios_decode:
        print(f"\n  decode measured/calibrated ratio:  min={min(ratios_decode):.2f}x  "
              f"max={max(ratios_decode):.2f}x  mean={sum(ratios_decode) / len(ratios_decode):.2f}x")
        print(f"  prefill measured/calibrated ratio: min={min(ratios_prefill):.2f}x  "
              f"max={max(ratios_prefill):.2f}x  mean={sum(ratios_prefill) / len(ratios_prefill):.2f}x")


def run_o1_sheets(wb):
    section("O1 interactive-capacity sweeps — ceiling & at-ceiling latency vs. idle roofline")
    print(f"{'sheet':<22} {'gpu':<9} {'prec':<4} {'ctx':>7} | {'decode meas':>13} {'calib':>8} {'m/calib':>8} "
          f"| {'prefill meas':>14} {'calib':>10} {'m/calib':>8} | {'ceil meas':>9} {'ceil pred(mem)':>14} {'ceil pred(SLA)':>14} {'bind':>8}")

    for sheet_name in ["July 2026 (O1 closed-loop)", "Aug 2026 (O1 H200)"]:
        ws = wb[sheet_name]
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        idx = {h: i for i, h in enumerate(headers)}

        for row in ws.iter_rows(min_row=2, values_only=True):
            gpu_name = norm_gpu(row[idx["gpu_model"]] or "")
            if not gpu_name or "qwen3.5-122b" not in (row[idx["model_id"]] or "").lower():
                continue
            precision = norm_precision(row[idx["precision"]] or "")
            context_length = row[idx["context_length_tokens"]]
            gpu_count = row[idx["gpu_count"]]
            concurrent_sessions = row[idx["concurrent_sessions"]]
            itl_p50 = row[idx["itl_p50_ms"]]
            ttft_p99 = row[idx["p99_ttft_ms_at_interactive_ceiling"]]
            if itl_p50 is None or ttft_p99 is None or not context_length:
                continue

            decode_raw, decode_cal, prefill_raw, prefill_cal = predict(
                gpu_name, precision, context_length, context_length, gpu_count,
                batch_size=concurrent_sessions,
            )
            measured_decode = 1000.0 / itl_p50
            measured_prefill = context_length / (ttft_p99 / 1000.0)

            gpu_mem_gb = gpu_mem_gb_from_model_string(row[idx["gpu_model"]])
            specs = GPU_SPECS[gpu_name]
            if gpu_mem_gb:
                predicted_mem_ceiling = calc_concurrent_users_support(
                    gpu_mem_gb * gpu_count, MODEL_TOTAL_PARAMS_B, precision, context_length,
                )
                sla_result = calc_interactive_ceiling(
                    gpu_mem_gb * gpu_count, MODEL_ACTIVE_PARAMS_B, precision, context_length,
                    specs["bf16"], specs["mem_bw"], gpu_count=gpu_count,
                )
                predicted_sla_ceiling, binding = sla_result.ceiling, sla_result.binding_constraint
            else:
                predicted_mem_ceiling, predicted_sla_ceiling, binding = None, None, "n/a"

            print(f"{sheet_name[:22]:<22} {gpu_name:<9} {precision:<4} {context_length:>7} | "
                  f"{measured_decode:>10.1f}tps {decode_cal:>8.1f} {ratio(measured_decode, decode_cal):>8} | "
                  f"{measured_prefill:>11.0f}tps {prefill_cal:>10.0f} {ratio(measured_prefill, prefill_cal):>8} | "
                  f"{concurrent_sessions:>9} {str(predicted_mem_ceiling):>14} {str(predicted_sla_ceiling):>14} {binding:>8}")


def main():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    run_june_sheet(wb)
    run_o1_sheets(wb)
    print(
        "\nNote: measured/calibrated ratios are expected to be < 1x — the engine models "
        "idealized single-stream roofline throughput, while every row here is real "
        "contended serving (batched decode / concurrent sessions). The ratio itself, "
        "and how it moves with concurrency and context length, is the signal to read: "
        "a stable ratio across rows means the roofline shape tracks reality (just needs "
        "a serving-efficiency factor); a ratio that swings a lot means the engine is "
        "missing a real effect (e.g. batching, contention, or a KV-cache term)."
    )


if __name__ == "__main__":
    main()
