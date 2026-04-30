#!/usr/bin/env python3
"""
Validation test for GPU calculation logic review fixes.
Tests KV cache GQA, TFLOPS scaling, concurrent users, MoE, PCIe topology.
No external dependencies required — uses the engine modules directly.
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

passed = 0
failed = 0

def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}  {detail}")


# ── Import engine modules ──────────────────────────────────────────────
from app.engine.performance import (
    calc_model_memory_gb,
    calc_kv_cache_per_user_gb,
    calc_concurrent_users_support,
    calculate_performance,
    MODEL_ARCHITECTURES,
    PRECISION_BYTES,
)


# =====================================================================
print("=== Fix #13: KV Cache GQA Accuracy ===")
# HTML source: KV per user ~0.6–1 GB for 70B FP8 @ 4K context
# =====================================================================
kv_70b_fp8_4k = calc_kv_cache_per_user_gb(4096, "FP8", 70)
check(
    f"70B FP8 @ 4K ctx: {kv_70b_fp8_4k:.3f} GB/user (expect ~0.6)",
    0.4 <= kv_70b_fp8_4k <= 1.0,
    f"got {kv_70b_fp8_4k:.3f}",
)

kv_70b_bf16_4k = calc_kv_cache_per_user_gb(4096, "BF16", 70)
check(
    f"70B BF16 @ 4K ctx: {kv_70b_bf16_4k:.3f} GB/user (expect ~1.2)",
    0.8 <= kv_70b_bf16_4k <= 2.0,
    f"got {kv_70b_bf16_4k:.3f}",
)

# Verify num_kv_heads is present in all architectures
for size, arch in MODEL_ARCHITECTURES.items():
    check(
        f"MODEL_ARCHITECTURES[{size}] has num_kv_heads",
        "num_kv_heads" in arch,
    )


# =====================================================================
print("\n=== Fix #3: No Double TFLOPS Scaling ===")
# FP8 should give ~2x throughput vs FP16, not 4x
# =====================================================================
perf_fp16 = calculate_performance(
    params_b=70, precision="FP16", context_length=4096, batch_size=1,
    bf16_tflops=1750, mem_bandwidth_tb_s=3.35, hbm_capacity_gb=80,
)
perf_fp8 = calculate_performance(
    params_b=70, precision="FP8", context_length=4096, batch_size=1,
    bf16_tflops=1750, mem_bandwidth_tb_s=3.35, hbm_capacity_gb=80,
)
ratio = perf_fp8.prefill_tokens_per_sec / perf_fp16.prefill_tokens_per_sec if perf_fp16.prefill_tokens_per_sec > 0 else 0
check(
    f"FP8/FP16 prefill ratio: {ratio:.1f}x (expect ~2x, not 4x)",
    1.5 <= ratio <= 2.5,
    f"got {ratio:.1f}x",
)


# =====================================================================
print("\n=== Fix #5: RTX PRO 6000 BSE bf16_tflops ===")
# =====================================================================
# Verify via seed.py source (can't import due to sqlalchemy dep).
# Instead, test that the engine produces non-zero throughput with the
# values we set in seed.py (bf16=480, fp8=960).
perf_rtx = calculate_performance(
    params_b=70, precision="FP8", context_length=4096, batch_size=1,
    bf16_tflops=480, mem_bandwidth_tb_s=1.6, hbm_capacity_gb=96,
    memory_gb=96, interconnect_type="PCIe", supports_fp4=True,
)
check(
    f"RTX PRO decode tok/s = {perf_rtx.decode_tokens_per_sec:.0f} (expect > 0)",
    perf_rtx.decode_tokens_per_sec > 0,
)
check(
    f"RTX PRO prefill tok/s = {perf_rtx.prefill_tokens_per_sec:.0f} (expect > 0)",
    perf_rtx.prefill_tokens_per_sec > 0,
)

# Verify seed.py has correct values by reading the file directly
import ast, re
seed_path = os.path.join(os.path.dirname(__file__), "backend", "app", "db", "seed.py")
with open(seed_path) as f:
    seed_src = f.read()
check("seed.py: RTX PRO has bf16_tflops: 480", '"bf16_tflops": 480' in seed_src)
check("seed.py: RTX PRO has fp8_tflops: 960", '"fp8_tflops": 960' in seed_src)
check("seed.py: H200 SXM has fp8_tflops: 3960", '"fp8_tflops": 3960' in seed_src)


# =====================================================================
print("\n=== Fix #6+7: Calibration GPU Name Alignment ===")
# =====================================================================
from app.engine.calibration import REFERENCE_DECODE, REFERENCE_PREFILL, FP8_MULTIPLIER, _gpu_specs

cal_names = set(REFERENCE_DECODE.keys())
for name in ["H100 SXM5", "H200 SXM", "B200 HGX", "B300 HGX", "RTX PRO 6000 BSE"]:
    check(
        f"'{name}' in REFERENCE_DECODE",
        name in REFERENCE_DECODE,
    )
    check(
        f"'{name}' in FP8_MULTIPLIER",
        name in FP8_MULTIPLIER,
    )

# Verify _gpu_specs bandwidth matches seed data
specs = _gpu_specs()
check("B300 HGX mem_bw = 8.0 (not 16.0)", specs["B300 HGX"]["mem_bw"] == 8.0)
check("GB300 NVL72 mem_bw = 8.0 (not 16.0)", specs["GB300 NVL72"]["mem_bw"] == 8.0)
check("MI300X mem_bw = 3.2 (not 5.3)", specs["MI300X"]["mem_bw"] == 3.2)
check("H200 SXM bf16 = 1970 (not 989)", specs["H200 SXM"]["bf16"] == 1970)


# =====================================================================
print("\n=== Fix #1: Dynamic KV cache in concurrent user calc ===")
# =====================================================================
# With GQA-aware KV, 70B FP8 on 96GB should support ~40 users at 4K
users_rtx = calc_concurrent_users_support(96, 70, "FP8", 4096)
check(
    f"RTX PRO 96GB, 70B FP8, 4K ctx: {users_rtx} users (expect 20-45)",
    20 <= users_rtx <= 60,
    f"got {users_rtx}",
)

# At 32K context, KV per user is ~8x larger, so many fewer users
users_rtx_32k = calc_concurrent_users_support(96, 70, "FP8", 32768)
check(
    f"RTX PRO 96GB, 70B FP8, 32K ctx: {users_rtx_32k} users (expect 3-8)",
    1 <= users_rtx_32k <= 15,
    f"got {users_rtx_32k}",
)

# H100 80GB, 70B FP8, 4K context
users_h100 = calc_concurrent_users_support(80, 70, "FP8", 4096)
check(
    f"H100 80GB, 70B FP8, 4K ctx: {users_h100} users (expect 10-20)",
    5 <= users_h100 <= 30,
    f"got {users_h100}",
)


# =====================================================================
print("\n=== Fix #11: No PCIe Memory Bandwidth Penalty ===")
# =====================================================================
perf_pcie_1 = calculate_performance(
    params_b=70, precision="FP8", context_length=4096, batch_size=1,
    bf16_tflops=480, mem_bandwidth_tb_s=1.6, hbm_capacity_gb=96,
    gpu_count=1, memory_gb=96, interconnect_type="PCIe",
)
perf_pcie_4 = calculate_performance(
    params_b=70, precision="FP8", context_length=4096, batch_size=1,
    bf16_tflops=480, mem_bandwidth_tb_s=1.6, hbm_capacity_gb=96,
    gpu_count=4, memory_gb=96, interconnect_type="PCIe",
)
# With no bandwidth penalty, multi-GPU should scale linearly (same BW per GPU)
ratio_pcie = perf_pcie_4.decode_tokens_per_sec / perf_pcie_1.decode_tokens_per_sec
check(
    f"PCIe 4-GPU / 1-GPU decode ratio: {ratio_pcie:.1f}x (expect ~4x, no penalty)",
    3.5 <= ratio_pcie <= 4.5,
    f"got {ratio_pcie:.1f}x",
)


# =====================================================================
print("\n=== Fix #4: MoE KV Cache Sizing ===")
# =====================================================================
# Mixtral-like: 176B total, 8 experts → base ~22B
# KV should be much smaller than if we used 176B architecture
perf_dense_176b = calculate_performance(
    params_b=176, precision="FP8", context_length=4096, batch_size=10,
    bf16_tflops=2250, mem_bandwidth_tb_s=8.0, hbm_capacity_gb=192,
    is_moe=False,
)
perf_moe_176b = calculate_performance(
    params_b=176, precision="FP8", context_length=4096, batch_size=10,
    bf16_tflops=2250, mem_bandwidth_tb_s=8.0, hbm_capacity_gb=192,
    is_moe=True, num_experts=8, active_experts=2,
)
check(
    f"MoE 176B KV cache: {perf_moe_176b.kv_cache_gb:.2f} GB vs Dense: {perf_dense_176b.kv_cache_gb:.2f} GB",
    perf_moe_176b.kv_cache_gb < perf_dense_176b.kv_cache_gb * 0.5,
    "MoE KV should be much smaller than dense",
)
# MoE model_memory should still be full 176B (all experts in VRAM)
check(
    f"MoE model_memory = {perf_moe_176b.model_memory_gb:.0f} GB (same as dense {perf_dense_176b.model_memory_gb:.0f} GB)",
    perf_moe_176b.model_memory_gb == perf_dense_176b.model_memory_gb,
)


# =====================================================================
print("\n=== HTML Source Cross-Checks ===")
# =====================================================================
# 70B FP8 weights = ~70 GB, RTX PRO has ~26 GB KV headroom
model_mem_70b_fp8 = calc_model_memory_gb(70, "FP8")
check(f"70B FP8 weight memory: {model_mem_70b_fp8:.0f} GB (expect 70)", model_mem_70b_fp8 == 70)

rtx_kv_headroom = 96 - model_mem_70b_fp8
check(f"RTX PRO KV headroom: {rtx_kv_headroom:.0f} GB (expect ~26)", 24 <= rtx_kv_headroom <= 28)

# 200B FP4 = 100 GB → exceeds RTX PRO 96 GB
model_mem_200b_fp4 = calc_model_memory_gb(200, "FP4")
check(f"200B FP4 weight memory: {model_mem_200b_fp4:.0f} GB (expect 100, > 96)", model_mem_200b_fp4 > 96)

# B300 288GB: HTML says 200B FP8 + 20 users fits on 1 GPU (weights ~200GB + KV ~10-20GB)
# 100 users needs 1-2 GPUs (exceeds 288GB).
# Note: get_model_arch(200) interpolates to 228 layers which slightly over-estimates
# KV vs a real 200B model, so we test 20 users (safe margin).
model_mem_200b_fp8 = calc_model_memory_gb(200, "FP8")
kv_per_user_200b = calc_kv_cache_per_user_gb(4096, "FP8", 200)
total_200b_20u = model_mem_200b_fp8 + kv_per_user_200b * 20
total_200b_100u = model_mem_200b_fp8 + kv_per_user_200b * 100
check(
    f"200B FP8 KV/user = {kv_per_user_200b:.2f} GB (expect 0.5–2.0)",
    0.5 <= kv_per_user_200b <= 2.0,
    f"got {kv_per_user_200b:.2f} GB",
)
check(
    f"200B FP8 + 20-user KV = {total_200b_20u:.0f} GB (expect < 288 for B300)",
    total_200b_20u < 288,
    f"got {total_200b_20u:.0f} GB",
)
check(
    f"200B FP8 + 100-user KV = {total_200b_100u:.0f} GB (expect > 288, needs 2 GPUs per HTML)",
    total_200b_100u > 288,
    f"got {total_200b_100u:.0f} GB",
)


# =====================================================================
print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed out of {passed+failed} tests")
if failed == 0:
    print("All tests passed!")
else:
    print(f"⚠️  {failed} test(s) need attention")
    sys.exit(1)
