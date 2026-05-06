"""Tests for the per-GPU calibration multipliers (decode + prefill + FP8/FP4).

Calibration sits between the roofline model and the reported throughput,
correcting roofline numbers against measured benchmark anchors. These tests
guard the residual-correction logic that prevents double-counting precision
boosts that performance.py already encodes via bytes-per-param.
"""

import pytest

from app.engine.calibration import (
    calibrate_decode,
    calibrate_prefill,
    get_decode_factor,
    get_prefill_factor,
    get_fp8_multiplier,
    REFERENCE_DECODE,
    REFERENCE_PREFILL,
)


class TestCalibration:
    def test_decode_factors_exist_for_all_gpus(self):
        for name in REFERENCE_DECODE:
            assert get_decode_factor(name) > 0

    def test_prefill_factors_exist_for_all_gpus(self):
        for name in REFERENCE_PREFILL:
            assert get_prefill_factor(name) > 0

    def test_calibrated_decode_h200_within_15pct(self):
        raw = 34.3  # roofline: 4.8 TB/s / (70B×2)
        calibrated = calibrate_decode("H200 SXM", raw, "FP16")
        ref = REFERENCE_DECODE["H200 SXM"]
        assert abs(calibrated - ref) / ref < 0.15

    def test_calibrated_decode_b200_within_15pct(self):
        raw = 57.1  # roofline: 8 TB/s / (70B×2)
        calibrated = calibrate_decode("B200 HGX", raw, "FP16")
        ref = REFERENCE_DECODE["B200 HGX"]
        assert abs(calibrated - ref) / ref < 0.15

    def test_calibrated_prefill_b200(self):
        raw = 16_071.0  # rough roofline
        calibrated = calibrate_prefill("B200 HGX", raw, "FP16")
        assert calibrated >= raw  # calibration should boost toward 45K

    def test_fp8_no_double_count(self):
        # GB200 measured FP8 ratio = 2.2 > theoretical 2.0 → no residual
        # correction. Calibration of FP8 raw should equal calibration of FP16
        # raw (the FP8 boost is encoded upstream in performance.py via
        # bytes-per-param, so calibration must NOT apply it again).
        fp16 = calibrate_decode("GB200 NVL72", 57.1, "FP16")
        fp8 = calibrate_decode("GB200 NVL72", 57.1, "FP8")
        assert fp8 == pytest.approx(fp16, rel=0.01)

    def test_fp8_residual_correction_for_b200(self):
        # B200 measured 1.9 vs theoretical 2.0 → residual 0.95 down-correction.
        fp16 = calibrate_decode("B200 HGX", 57.1, "FP16")
        fp8 = calibrate_decode("B200 HGX", 57.1, "FP8")
        assert fp8 == pytest.approx(fp16 * (1.9 / 2.0), rel=0.01)

    def test_fp8_down_corrects_weak_hardware(self):
        # MI300X has weak FP8 (multiplier 1.0 vs theoretical 2.0) → calibrated
        # FP8 should be half of calibrated FP16 to compensate for the upstream
        # 2× boost that this GPU cannot actually deliver.
        fp16 = calibrate_decode("MI300X", 50.0, "FP16")
        fp8 = calibrate_decode("MI300X", 50.0, "FP8")
        assert fp8 == pytest.approx(fp16 * 0.5, rel=0.02)

    def test_fp4_residual_for_b300(self):
        # B300 measured FP8 ratio 2.1; using as proxy for FP4 vs theoretical 4.0
        # → residual = 2.1 / 4.0 = 0.525. Calibrated FP4 should be that
        # fraction of calibrated FP16 (since the 4× FP4 boost is upstream).
        fp16 = calibrate_decode("B300 HGX", 100.0, "FP16")
        fp4 = calibrate_decode("B300 HGX", 100.0, "FP4")
        assert fp4 == pytest.approx(fp16 * (2.1 / 4.0), rel=0.02)

    def test_unknown_gpu_factor_is_1(self):
        assert get_decode_factor("FakeGPU 9000") == 1.0
        assert get_prefill_factor("FakeGPU 9000") == 1.0

    def test_fp8_unknown_gpu_is_1(self):
        assert get_fp8_multiplier("FakeGPU 9000") == 1.0

    def test_calibration_is_deterministic(self):
        a = calibrate_decode("MI300X", 50.0, "FP16")
        b = calibrate_decode("MI300X", 50.0, "FP16")
        assert a == b
