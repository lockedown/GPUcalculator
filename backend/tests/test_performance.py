"""Unit tests for the performance calculation engine."""

import pytest
from app.engine.performance import (
    calc_model_memory_gb,
    calc_kv_cache_gb,
    calc_prefill_tokens_per_sec,
    calc_decode_tokens_per_sec,
    calc_max_context_tokens,
    calculate_performance,
    get_model_arch,
    PRECISION_BYTES,
)


class TestModelMemory:
    def test_70b_fp16(self):
        mem = calc_model_memory_gb(70, "FP16")
        assert mem == pytest.approx(140.0, rel=0.01)

    def test_70b_fp8(self):
        mem = calc_model_memory_gb(70, "FP8")
        assert mem == pytest.approx(70.0, rel=0.01)

    def test_7b_fp16(self):
        mem = calc_model_memory_gb(7, "FP16")
        assert mem == pytest.approx(14.0, rel=0.01)

    def test_405b_fp8(self):
        mem = calc_model_memory_gb(405, "FP8")
        assert mem == pytest.approx(405.0, rel=0.01)

    def test_1500b_fp4(self):
        mem = calc_model_memory_gb(1500, "FP4")
        assert mem == pytest.approx(750.0, rel=0.01)


class TestKVCache:
    def test_llama70b_4k_ctx(self):
        # Llama3-70B: 80 layers, 8192 hidden_dim
        kv = calc_kv_cache_gb(80, 8192, 4096, 1, "FP16")
        # 2 * 80 * 8192 * 4096 * 2 * 1 = ~10.7 GB
        assert kv == pytest.approx(10.0, rel=0.15)

    def test_kv_scales_with_batch(self):
        kv_b1 = calc_kv_cache_gb(80, 8192, 4096, 1, "FP16")
        kv_b8 = calc_kv_cache_gb(80, 8192, 4096, 8, "FP16")
        assert kv_b8 == pytest.approx(kv_b1 * 8, rel=0.01)

    def test_kv_scales_with_context(self):
        kv_4k = calc_kv_cache_gb(80, 8192, 4096, 1, "FP16")
        kv_128k = calc_kv_cache_gb(80, 8192, 131072, 1, "FP16")
        assert kv_128k == pytest.approx(kv_4k * 32, rel=0.01)

    def test_fp8_halves_kv(self):
        kv_fp16 = calc_kv_cache_gb(80, 8192, 4096, 1, "FP16")
        kv_fp8 = calc_kv_cache_gb(80, 8192, 4096, 1, "FP8")
        assert kv_fp8 == pytest.approx(kv_fp16 / 2, rel=0.01)


class TestDecodeTokensPerSec:
    """Decode is memory-BW-bound: tok/s = mem_bw / (params * bytes_per_param)."""

    def test_h200_70b_fp16(self):
        # H200: 4.8 TB/s, 70B FP16 → 4.8e12 / (70e9 * 2) = ~34 tok/s
        tps = calc_decode_tokens_per_sec(4.8, 70, "FP16")
        assert tps == pytest.approx(34.3, rel=0.05)

    def test_b200_70b_fp16(self):
        # B200: 8 TB/s, 70B FP16 → 8e12 / (70e9 * 2) = ~57 tok/s
        tps = calc_decode_tokens_per_sec(8.0, 70, "FP16")
        assert tps == pytest.approx(57.1, rel=0.05)

    def test_b300_70b_fp16(self):
        # B300: 8 TB/s HBM3e (same per-stack BW as B200, more capacity)
        # → 8e12 / (70e9 * 2) = ~57 tok/s
        tps = calc_decode_tokens_per_sec(8.0, 70, "FP16")
        assert tps == pytest.approx(57.1, rel=0.05)

    def test_fp8_doubles_throughput(self):
        tps_fp16 = calc_decode_tokens_per_sec(8.0, 70, "FP16")
        tps_fp8 = calc_decode_tokens_per_sec(8.0, 70, "FP8")
        assert tps_fp8 == pytest.approx(tps_fp16 * 2, rel=0.01)

    def test_7b_single_gpu_fast(self):
        # H200 + 7B FP8 → 4.8e12 / (7e9 * 1) = ~686 tok/s
        tps = calc_decode_tokens_per_sec(4.8, 7, "FP8")
        assert tps == pytest.approx(685.7, rel=0.05)


class TestPrefillTokensPerSec:
    def test_returns_positive(self):
        tps, _ = calc_prefill_tokens_per_sec(989, 70, "FP16", 4.8)
        assert tps > 0

    def test_fp8_faster_than_fp16(self):
        tps_16, _ = calc_prefill_tokens_per_sec(989, 70, "FP16", 4.8)
        tps_8, _ = calc_prefill_tokens_per_sec(989, 70, "FP8", 4.8)
        assert tps_8 > tps_16


class TestMaxContextTokens:
    def test_h200_70b_fp16(self):
        # H200 141GB, 70B FP16 → model = 140GB, only 1GB left → small context
        max_ctx = calc_max_context_tokens(141, 140, 80, 8192, "FP16", 1)
        assert max_ctx > 0
        assert max_ctx < 100000

    def test_multi_gpu_extends_context(self):
        ctx_1 = calc_max_context_tokens(192, 140, 80, 8192, "FP16", 1)
        ctx_2 = calc_max_context_tokens(192, 140, 80, 8192, "FP16", 2)
        assert ctx_2 > ctx_1

    def test_zero_when_model_too_large(self):
        ctx = calc_max_context_tokens(141, 200, 80, 8192, "FP16", 1)
        assert ctx == 0


class TestCalculatePerformance:
    def test_70b_h200(self):
        result = calculate_performance(
            params_b=70, precision="FP16", context_length=4096,
            batch_size=1, bf16_tflops=989, mem_bandwidth_tb_s=4.8,
            hbm_capacity_gb=141, gpu_count=1,
        )
        assert result.decode_tokens_per_sec > 0
        assert result.prefill_tokens_per_sec > 0
        assert result.kv_cache_gb > 0
        assert result.model_memory_gb == pytest.approx(140.0, rel=0.01)
        assert result.is_memory_bw_bound_decode is True

    def test_multi_gpu_scales_bandwidth(self):
        r1 = calculate_performance(
            params_b=70, precision="FP16", context_length=4096,
            batch_size=1, bf16_tflops=989, mem_bandwidth_tb_s=4.8,
            hbm_capacity_gb=141, gpu_count=1,
        )
        r2 = calculate_performance(
            params_b=70, precision="FP16", context_length=4096,
            batch_size=1, bf16_tflops=989, mem_bandwidth_tb_s=4.8,
            hbm_capacity_gb=141, gpu_count=2,
        )
        assert r2.decode_tokens_per_sec > r1.decode_tokens_per_sec
