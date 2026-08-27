"""Tests for the per-GPU calibration multipliers (decode + prefill + FP8/FP4).

Calibration sits between the roofline model and the reported throughput,
correcting roofline numbers against measured benchmark anchors. These tests
guard the residual-correction logic that prevents double-counting precision
boosts that performance.py already encodes via bytes-per-param.
"""

import pytest

from app.engine.calibration import (
    CALIBRATION_VERSION,
    calibrate_decode,
    calibrate_prefill,
    get_decode_factor,
    get_prefill_factor,
    get_fp8_multiplier,
    REFERENCE_DECODE,
    REFERENCE_PREFILL,
)


# ---------------------------------------------------------------------------
# Drift snapshot — frozen copy of REFERENCE_DECODE / REFERENCE_PREFILL as of
# CALIBRATION_VERSION above. The test below pins the live tables to these
# values; if you intentionally refresh the calibration anchors against a new
# benchmark snapshot, bump CALIBRATION_VERSION *and* update both snapshots
# below in the same commit. The two-step lockstep is the whole point — it
# makes silent drift impossible.
# ---------------------------------------------------------------------------
_REFERENCE_DECODE_SNAPSHOT_2026_08_27: dict[str, float] = {
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
    # Added Aug 2026 — pre-GA extrapolations, see calibration.py module docstring.
    "Vera Rubin NVL72": 560.0,
    "Rubin CPX": 45.0,
    "MI450X": 200.0,
    "MI455X": 230.0,
}

_REFERENCE_PREFILL_SNAPSHOT_2026_08_27: dict[str, float] = {
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
    # Added Aug 2026 — pre-GA extrapolations, see calibration.py module docstring.
    "Vera Rubin NVL72": 210_000.0,
    "Rubin CPX": 95_000.0,
    "MI450X": 80_000.0,
    "MI455X": 95_000.0,
}


class TestCalibrationFreshness:
    """Lock down the calibration table against silent drift. Together with
    CALIBRATION_VERSION bumps, this enforces a "version + values move together"
    invariant whenever the benchmark anchors are refreshed.
    """

    def test_calibration_version_is_iso_date(self):
        assert isinstance(CALIBRATION_VERSION, str)
        assert len(CALIBRATION_VERSION) == 10
        assert CALIBRATION_VERSION[4] == "-" and CALIBRATION_VERSION[7] == "-"

    def test_reference_decode_matches_snapshot(self):
        # When updating the calibration anchors against fresh MLPerf / vLLM /
        # NVIDIA benchmark data, edit BOTH the live table in calibration.py AND
        # the matching snapshot above, AND bump CALIBRATION_VERSION. A drift
        # without those three things in lockstep is exactly what this test
        # catches.
        assert REFERENCE_DECODE == _REFERENCE_DECODE_SNAPSHOT_2026_08_27, (
            "REFERENCE_DECODE drifted from the snapshot. If this is intentional, "
            "update _REFERENCE_DECODE_SNAPSHOT_2026_08_27 (rename to today's "
            "date) and bump CALIBRATION_VERSION in calibration.py."
        )

    def test_reference_prefill_matches_snapshot(self):
        assert REFERENCE_PREFILL == _REFERENCE_PREFILL_SNAPSHOT_2026_08_27, (
            "REFERENCE_PREFILL drifted from the snapshot. Same drill: update "
            "the snapshot + CALIBRATION_VERSION together."
        )

    def test_snapshot_covers_all_seeded_gpus(self):
        # Sanity check that the snapshot didn't lose a GPU when calibration
        # was extended for a new SKU (which would be a drift in the other
        # direction — silent under-coverage).
        assert set(_REFERENCE_DECODE_SNAPSHOT_2026_08_27) == set(REFERENCE_DECODE)
        assert set(_REFERENCE_PREFILL_SNAPSHOT_2026_08_27) == set(REFERENCE_PREFILL)


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
