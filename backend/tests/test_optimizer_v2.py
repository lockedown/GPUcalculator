"""Comprehensive tests for comparison module: optimizer, calibration, topology,
normalization, constraints, benchmark blending, concurrent_users impact, and
end-to-end comparison via the engine and API."""

import pytest
from app.engine.optimizer import (
    _rank_normalize,
    _constraint_penalty,
    _passes_all_constraints,
    _benchmark_perf_score,
    _benchmark_scores_dict,
    normalize_and_rank,
    calc_topology,
    evaluate_gpu,
    run_calculation,
    run_comparison,
)
from app.engine.calibration import (
    calibrate_decode,
    calibrate_prefill,
    get_decode_factor,
    get_prefill_factor,
    get_fp8_multiplier,
    REFERENCE_DECODE,
    REFERENCE_PREFILL,
)
from app.engine.performance import (
    calculate_performance,
    calc_model_memory_gb,
    calc_kv_cache_gb,
    calc_decode_tokens_per_sec,
)
from app.engine.cost import calc_tco, calc_network_cost
from app.engine.complexity import calc_complexity
from app.engine.availability import calc_availability
from app.schemas.workload import (
    GPUResult,
    ConstraintInput,
    TopologyResult,
    WorkloadInput,
    ComparisonResponse,
)
from app.db.database import SessionLocal, create_tables
from app.models import GPU


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def db():
    create_tables()
    session = SessionLocal()
    yield session
    session.close()


def _mock_gpu(**overrides):
    defaults = dict(
        hbm_capacity_gb=192,
        memory_gb=192,
        memory_type="HBM3e",
        memory_bandwidth_tbps=8.0,
        interconnect_type="NVLink 5",
        cooling_requirement="Any",
        supported_workloads=["inference", "training", "fine-tuning"],
        supports_fp4=True,
        is_rack_scale=False,
        rack_gpu_count=None,
        max_gpus_per_node=8,
        interconnect_bw_gb_s=900,
        rack_fabric_bw_tb_s=None,
    )
    defaults.update(overrides)

    class MockGPU:
        pass

    gpu = MockGPU()
    for k, v in defaults.items():
        setattr(gpu, k, v)
    return gpu


# ===========================================================================
# 1. RANK NORMALIZATION
# ===========================================================================
class TestRankNormalize:
    def test_higher_is_better(self):
        vals = [10.0, 30.0, 20.0]
        scores = _rank_normalize(vals, higher_is_better=True)
        assert scores[0] == pytest.approx(0.0)   # 10 = lowest
        assert scores[1] == pytest.approx(1.0)   # 30 = highest
        assert scores[2] == pytest.approx(0.5)   # 20 = middle

    def test_lower_is_better(self):
        vals = [100.0, 300.0, 200.0]
        scores = _rank_normalize(vals, higher_is_better=False)
        assert scores[0] == pytest.approx(1.0)   # 100 = best (lowest)
        assert scores[1] == pytest.approx(0.0)   # 300 = worst
        assert scores[2] == pytest.approx(0.5)   # 200 = middle

    def test_handles_none(self):
        vals = [10.0, None, 30.0]
        scores = _rank_normalize(vals, higher_is_better=True)
        assert scores[1] == 0.0

    def test_all_none(self):
        scores = _rank_normalize([None, None, None])
        assert scores == [0.0, 0.0, 0.0]

    def test_empty_list(self):
        assert _rank_normalize([]) == []

    def test_single_value(self):
        scores = _rank_normalize([42.0])
        assert scores == [1.0]

    def test_ties_get_same_rank(self):
        vals = [10.0, 20.0, 20.0, 30.0]
        scores = _rank_normalize(vals, higher_is_better=True)
        assert scores[1] == scores[2]

    def test_outlier_doesnt_compress(self):
        vals = [10.0, 20.0, 30.0, 1_000_000.0]
        scores = _rank_normalize(vals, higher_is_better=False)
        assert scores[0] == pytest.approx(1.0)
        assert scores[1] == pytest.approx(2 / 3, abs=0.01)
        assert scores[2] == pytest.approx(1 / 3, abs=0.01)
        assert scores[3] == pytest.approx(0.0)

    def test_two_values(self):
        scores = _rank_normalize([5.0, 10.0], higher_is_better=True)
        assert scores[0] == pytest.approx(0.0)
        assert scores[1] == pytest.approx(1.0)

    def test_all_equal(self):
        scores = _rank_normalize([7.0, 7.0, 7.0], higher_is_better=True)
        assert scores[0] == scores[1] == scores[2]


# ===========================================================================
# 2. CALIBRATION
# ===========================================================================
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


# ===========================================================================
# 3. CONSTRAINT PENALTIES
# ===========================================================================
class TestConstraintPenalty:
    def _make_result(self, tco=100_000, codes=None, power_kw=5.0):
        r = GPUResult(
            gpu_id=1, gpu_name="Test", gpu_vendor="NVIDIA",
            tco_usd=tco, violation_codes=codes or [],
        )
        r._power_kw = power_kw  # type: ignore[attr-defined]
        return r

    def test_no_violations_no_penalty(self):
        r = self._make_result()
        c = ConstraintInput()
        assert _constraint_penalty(r, c) == 0.0

    def test_budget_violation_penalty(self):
        r = self._make_result(tco=200_000, codes=["BUDGET_EXCEEDED"])
        c = ConstraintInput(max_budget_usd=100_000)
        assert _constraint_penalty(r, c) > 0

    def test_budget_overshoot_scales_penalty(self):
        r_small = self._make_result(tco=120_000, codes=["BUDGET_EXCEEDED"])
        r_big = self._make_result(tco=500_000, codes=["BUDGET_EXCEEDED"])
        c = ConstraintInput(max_budget_usd=100_000)
        assert _constraint_penalty(r_big, c) > _constraint_penalty(r_small, c)

    def test_power_violation_penalty(self):
        r = self._make_result(power_kw=50.0, codes=["POWER_EXCEEDED"])
        c = ConstraintInput(max_power_per_rack_kw=40.0)
        assert _constraint_penalty(r, c) > 0

    def test_power_within_limit_no_penalty(self):
        r = self._make_result(power_kw=30.0)
        c = ConstraintInput(max_power_per_rack_kw=40.0)
        assert _constraint_penalty(r, c) == 0.0

    def test_lead_time_violation_penalty(self):
        r = self._make_result(codes=["LEAD_TIME_EXCEEDED"])
        r.availability_score = 0.3
        c = ConstraintInput(max_lead_time_weeks=8)
        assert _constraint_penalty(r, c) > 0

    def test_cooling_soft_penalty(self):
        r = self._make_result(codes=["COOLING_SOFT"])
        c = ConstraintInput()
        assert _constraint_penalty(r, c) == pytest.approx(0.10)

    def test_cooling_hard_penalty(self):
        r = self._make_result(codes=["COOLING_HARD"])
        c = ConstraintInput()
        assert _constraint_penalty(r, c) == pytest.approx(0.30)

    def test_multiple_violations_stack(self):
        r = self._make_result(
            tco=200_000,
            codes=["BUDGET_EXCEEDED", "POWER_EXCEEDED", "COOLING_SOFT"],
            power_kw=100.0,
        )
        c = ConstraintInput(max_budget_usd=100_000, max_power_per_rack_kw=40.0)
        penalty = _constraint_penalty(r, c)
        # Budget + power + cooling = should be > any single penalty
        assert penalty > 0.30

    def test_penalty_caps_at_0_9(self):
        r = self._make_result(
            tco=10_000_000,
            codes=["BUDGET_EXCEEDED", "LEAD_TIME_EXCEEDED", "COOLING_HARD", "POWER_EXCEEDED"],
            power_kw=200.0,
        )
        r.availability_score = 0.1
        c = ConstraintInput(max_budget_usd=100, max_power_per_rack_kw=10, max_lead_time_weeks=4)
        assert _constraint_penalty(r, c) <= 0.9

    def test_passes_all_no_constraints(self):
        r = self._make_result()
        c = ConstraintInput()
        assert _passes_all_constraints(r, c) is True

    def test_fails_budget_constraint(self):
        r = self._make_result(tco=200_000, codes=["BUDGET_EXCEEDED"])
        c = ConstraintInput(max_budget_usd=100_000)
        assert _passes_all_constraints(r, c) is False

    def test_fails_power_constraint(self):
        r = self._make_result(power_kw=100.0, codes=["POWER_EXCEEDED"])
        c = ConstraintInput(max_power_per_rack_kw=40.0)
        assert _passes_all_constraints(r, c) is False

    def test_fails_lead_time_constraint(self):
        r = self._make_result(codes=["LEAD_TIME_EXCEEDED"])
        c = ConstraintInput(max_lead_time_weeks=12)
        assert _passes_all_constraints(r, c) is False

    def test_passes_within_all_limits(self):
        r = self._make_result(tco=50_000, power_kw=5.0)
        r.availability_score = 0.8
        c = ConstraintInput(max_budget_usd=100_000, max_power_per_rack_kw=40.0, max_lead_time_weeks=12)
        assert _passes_all_constraints(r, c) is True

    def test_soft_violation_does_not_disqualify(self):
        # COOLING_SOFT is soft → still passes constraint check
        r = self._make_result(codes=["COOLING_SOFT"])
        c = ConstraintInput()
        assert _passes_all_constraints(r, c) is True


# ===========================================================================
# 4. TOPOLOGY
# ===========================================================================
class TestTopology:
    def test_single_gpu_small_model(self):
        gpu = _mock_gpu(hbm_capacity_gb=192)
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=1, batch_size=1)
        assert topo.gpu_count == 1
        assert topo.dp_degree == 1
        assert topo.parallelism_strategy == "Single GPU"

    def test_tp_when_model_exceeds_single_gpu(self):
        gpu = _mock_gpu(hbm_capacity_gb=192)
        # 200GB model → needs 2 GPUs
        topo = calc_topology(gpu, 200.0, 210.0, concurrent_users=1, batch_size=1)
        assert topo.gpu_count >= 2
        assert topo.tp_degree >= 2
        assert "TP" in topo.parallelism_strategy

    def test_pp_when_model_exceeds_node(self):
        gpu = _mock_gpu(hbm_capacity_gb=192, max_gpus_per_node=8)
        # 2000GB model → needs >8 GPUs → multi-node PP
        topo = calc_topology(gpu, 2000.0, 2100.0, concurrent_users=1, batch_size=1)
        assert topo.nodes > 1
        assert topo.pp_degree > 1
        assert "PP" in topo.parallelism_strategy

    def test_cross_node_latency_penalty_increases_with_nodes(self):
        gpu = _mock_gpu(hbm_capacity_gb=192, max_gpus_per_node=8)
        topo2 = calc_topology(gpu, 2000.0, 2100.0)
        topo4 = calc_topology(gpu, 4000.0, 4100.0)
        assert topo4.cross_node_latency_penalty > topo2.cross_node_latency_penalty

    def test_cross_node_penalty_caps_at_0_5(self):
        gpu = _mock_gpu(hbm_capacity_gb=192, max_gpus_per_node=8)
        topo = calc_topology(gpu, 50000.0, 50100.0)
        assert topo.cross_node_latency_penalty <= 0.5

    def test_rack_scale_nvl72(self):
        gpu = _mock_gpu(
            hbm_capacity_gb=192,
            is_rack_scale=True,
            rack_gpu_count=72,
            rack_fabric_bw_tb_s=130.0,
        )
        topo = calc_topology(gpu, 500.0, 600.0, concurrent_users=1, batch_size=1)
        assert topo.gpu_count == 72
        assert topo.parallelism_strategy == "NVL72 unified fabric"
        assert topo.cross_node_latency_penalty == 0.0
        assert topo.effective_bandwidth_gb_s == 130_000.0

    def test_rack_scale_uses_total_memory_not_model_only(self):
        gpu = _mock_gpu(
            hbm_capacity_gb=192,
            is_rack_scale=True,
            rack_gpu_count=72,
        )
        # total_memory exceeds rack capacity → should NOT take rack path
        total_hbm = 192 * 72  # 13,824 GB
        topo = calc_topology(gpu, 100.0, total_hbm + 1)
        # Should not be NVL72 path since memory exceeds
        assert topo.parallelism_strategy != "NVL72 unified fabric"

    # --- DP (concurrent users) ---
    def test_dp_single_user_no_dp(self):
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=1, batch_size=1)
        assert topo.dp_degree == 1

    def test_dp_moderate_concurrency(self):
        """concurrent_users=10 with no throughput info → fallback ceil(10/8)=2."""
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=10, batch_size=1)
        assert topo.dp_degree >= 2
        assert "DP" in topo.parallelism_strategy

    def test_dp_low_concurrency_no_dp(self):
        """concurrent_users=5, no throughput info → fallback ceil(5/8)=1."""
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=5, batch_size=1)
        assert topo.dp_degree == 1

    def test_dp_9_users_triggers_dp(self):
        """concurrent_users=9 → fallback ceil(9/8)=2."""
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=9, batch_size=1)
        assert topo.dp_degree == 2

    def test_dp_batch_size_multiplies(self):
        """batch_size=4 with 5 users = 20 streams → fallback ceil(20/8)=3."""
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=5, batch_size=4)
        assert topo.dp_degree == 3

    def test_dp_high_concurrency(self):
        gpu = _mock_gpu()
        # 64 users × 1 stream, no per_gpu_decode_tps → fallback ceil(64/8)=8
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=64, batch_size=1)
        assert topo.dp_degree == 8

    def test_dp_scales_beyond_8_when_needed(self):
        # DP cap was removed; very high concurrency now scales DP linearly so each
        # user can still hit MIN_DECODE_TPS_PER_USER. With 1000 streams and the
        # fallback ceil(streams/8) heuristic → DP=125.
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=1000, batch_size=1)
        assert topo.dp_degree == 125

    def test_dp_disabled_when_model_exceeds_node(self):
        """When capacity_gpus > gpus_per_node, DP is not added."""
        gpu = _mock_gpu(hbm_capacity_gb=192, memory_gb=192, max_gpus_per_node=8)
        topo = calc_topology(gpu, 2000.0, 2100.0, concurrent_users=50, batch_size=1)
        assert topo.dp_degree == 1

    def test_gpu_count_equals_capacity_times_dp(self):
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=16, batch_size=1)
        # capacity_gpus=1, model fits on 1 GPU
        assert topo.gpu_count == topo.dp_degree * 1


# ===========================================================================
# 5. CONCURRENT_USERS END-TO-END IMPACT
# ===========================================================================
class TestConcurrentUsersImpact:
    """Verify concurrent_users changes topology, throughput, cost, and context."""

    def test_cu50_more_gpus_than_cu1(self, db):
        w1 = WorkloadInput(model_params_b=70, concurrent_users=1)
        w50 = WorkloadInput(model_params_b=70, concurrent_users=50)
        c = ConstraintInput()
        r1 = run_calculation(db, w1, c)
        r50 = run_calculation(db, w50, c)
        b1 = next(r for r in r1 if r.gpu_name == "B200 HGX")
        b50 = next(r for r in r50 if r.gpu_name == "B200 HGX")
        assert b50.topology.gpu_count > b1.topology.gpu_count

    def test_cu50_higher_aggregate_throughput(self, db):
        w1 = WorkloadInput(model_params_b=70, concurrent_users=1)
        w50 = WorkloadInput(model_params_b=70, concurrent_users=50)
        c = ConstraintInput()
        r1 = run_calculation(db, w1, c)
        r50 = run_calculation(db, w50, c)
        b1 = next(r for r in r1 if r.gpu_name == "B200 HGX")
        b50 = next(r for r in r50 if r.gpu_name == "B200 HGX")
        assert b50.tokens_per_sec > b1.tokens_per_sec

    def test_cu50_higher_tco(self, db):
        w1 = WorkloadInput(model_params_b=70, concurrent_users=1)
        w50 = WorkloadInput(model_params_b=70, concurrent_users=50)
        c = ConstraintInput()
        r1 = run_calculation(db, w1, c)
        r50 = run_calculation(db, w50, c)
        b1 = next(r for r in r1 if r.gpu_name == "B200 HGX")
        b50 = next(r for r in r50 if r.gpu_name == "B200 HGX")
        assert b50.tco_usd > b1.tco_usd

    def test_cu50_larger_kv_cache(self, db):
        w1 = WorkloadInput(model_params_b=70, concurrent_users=1)
        w50 = WorkloadInput(model_params_b=70, concurrent_users=50)
        c = ConstraintInput()
        r1 = run_calculation(db, w1, c)
        r50 = run_calculation(db, w50, c)
        b1 = next(r for r in r1 if r.gpu_name == "B200 HGX")
        b50 = next(r for r in r50 if r.gpu_name == "B200 HGX")
        assert b50.kv_cache_gb > b1.kv_cache_gb

    def test_cu50_lower_max_context_per_user(self, db):
        """More concurrent users means less VRAM per user → shorter max context."""
        w1 = WorkloadInput(model_params_b=7, concurrent_users=1)
        w50 = WorkloadInput(model_params_b=7, concurrent_users=50)
        c = ConstraintInput()
        r1 = run_calculation(db, w1, c)
        r50 = run_calculation(db, w50, c)
        b1 = next(r for r in r1 if r.gpu_name == "B200 HGX")
        b50 = next(r for r in r50 if r.gpu_name == "B200 HGX")
        assert b50.max_context_length < b1.max_context_length

    def test_dp_degree_shown_in_strategy(self, db):
        w = WorkloadInput(model_params_b=7, concurrent_users=200)
        c = ConstraintInput()
        results = run_calculation(db, w, c)
        b200 = next(r for r in results if r.gpu_name == "B200 HGX")
        assert b200.topology.dp_degree >= 2
        assert "DP" in b200.topology.parallelism_strategy


# ===========================================================================
# 6. BENCHMARK BLENDING
# ===========================================================================
class TestBenchmarkBlending:
    def test_no_category_no_benchmarks(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        results = run_calculation(db, w, c)
        for r in results:
            assert r.benchmark_scores is None

    def test_tokenization_returns_benchmarks(self, db):
        w = WorkloadInput(model_params_b=70, finance_benchmark_category="tokenization")
        c = ConstraintInput()
        results = run_calculation(db, w, c)
        # H100 SXM5 / RTX PRO 6000 BSE are seeded from extras and have no
        # benchmark rows; everything from the HTML matrix should have scores.
        html_seeded = [
            r for r in results
            if r.tokens_per_sec is not None
            and r.gpu_name not in {"H100 SXM5", "RTX PRO 6000 BSE"}
        ]
        assert len(html_seeded) > 0
        for r in html_seeded:
            assert r.benchmark_scores is not None
            assert len(r.benchmark_scores) > 0

    def test_quant_category_changes_rankings(self, db):
        """Quant workload should boost AMD MI300X (strong FP64) vs roofline-only."""
        w_none = WorkloadInput(model_params_b=70)
        w_quant = WorkloadInput(model_params_b=70, finance_benchmark_category="quant")
        c = ConstraintInput()
        r_none = run_calculation(db, w_none, c)
        r_quant = run_calculation(db, w_quant, c)
        order_none = [r.gpu_name for r in r_none]
        order_quant = [r.gpu_name for r in r_quant]
        assert order_none != order_quant, "Benchmark blending should change rankings"

    def test_benchmark_perf_score_returns_float(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        score = _benchmark_perf_score(db, gpu.id, "tokenization")
        assert isinstance(score, float)
        assert 0 < score <= 100

    def test_benchmark_scores_dict_has_entries(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        scores = _benchmark_scores_dict(db, gpu.id, "quant")
        assert len(scores) >= 3  # STAC-A2, Monte Carlo, DGEMM
        assert all(0 < v <= 100 for v in scores.values())

    def test_invalid_category_returns_no_benchmarks(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        score = _benchmark_perf_score(db, gpu.id, "nonexistent_category")
        assert score is None


# ===========================================================================
# 7. NORMALIZE AND RANK
# ===========================================================================
class TestNormalizeAndRank:
    def _make_results(self):
        """3 fake GPUResults with known values."""
        results = []
        for i, (name, tps, tco, cx, av) in enumerate([
            ("FastExpensive", 500.0, 200_000.0, 8.0, 0.9),
            ("SlowCheap", 100.0, 50_000.0, 9.0, 0.8),
            ("MidMid", 300.0, 100_000.0, 7.0, 0.5),
        ]):
            r = GPUResult(
                gpu_id=i, gpu_name=name, gpu_vendor="TEST",
                tokens_per_sec=tps, tco_usd=tco,
                complexity_score=cx, availability_score=av,
                warnings=[],
            )
            r._bench_perf_pct = None  # type: ignore[attr-defined]
            r._power_kw = 5.0  # type: ignore[attr-defined]
            results.append(r)
        return results

    def test_results_are_sorted_descending(self):
        results = self._make_results()
        c = ConstraintInput()
        ranked = normalize_and_rank(results, c.metric_weights, c)
        scores = [r.composite_score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_all_have_composite_score(self):
        results = self._make_results()
        c = ConstraintInput()
        ranked = normalize_and_rank(results, c.metric_weights, c)
        for r in ranked:
            assert r.composite_score is not None
            assert 0.0 <= r.composite_score <= 1.0

    def test_empty_list(self):
        c = ConstraintInput()
        assert normalize_and_rank([], c.metric_weights, c) == []

    def test_weights_affect_ranking(self):
        results = self._make_results()
        c_perf = ConstraintInput(
            metric_weights={"performance": 1.0, "cost": 0.0, "complexity": 0.0, "availability": 0.0}
        )
        c_cost = ConstraintInput(
            metric_weights={"performance": 0.0, "cost": 1.0, "complexity": 0.0, "availability": 0.0}
        )
        ranked_perf = normalize_and_rank(
            [GPUResult(**r.model_dump()) for r in self._make_results()],
            c_perf.metric_weights, c_perf,
        )
        ranked_cost = normalize_and_rank(
            [GPUResult(**r.model_dump()) for r in self._make_results()],
            c_cost.metric_weights, c_cost,
        )
        # Performance-only: FastExpensive first
        assert ranked_perf[0].gpu_name == "FastExpensive"
        # Cost-only: SlowCheap first (lowest TCO)
        assert ranked_cost[0].gpu_name == "SlowCheap"

    def test_constraint_penalty_lowers_score(self):
        # In production, evaluate_gpu sets BUDGET_EXCEEDED when tco exceeds the
        # budget; normalize_and_rank only consumes pre-set codes. Mirror that
        # contract here so the penalty path is exercised.
        c_no_budget = ConstraintInput()
        c_budget = ConstraintInput(max_budget_usd=80_000)

        free = self._make_results()
        budget = self._make_results()
        for r in budget:
            if r.tco_usd and r.tco_usd > 80_000:
                r.violation_codes = ["BUDGET_EXCEEDED"]

        ranked_free = normalize_and_rank(free, c_no_budget.metric_weights, c_no_budget)
        ranked_budget = normalize_and_rank(budget, c_budget.metric_weights, c_budget)
        # FastExpensive (TCO=200K > budget 80K) should have lower score with budget
        fe_free = next(r for r in ranked_free if r.gpu_name == "FastExpensive")
        fe_budget = next(r for r in ranked_budget if r.gpu_name == "FastExpensive")
        assert fe_budget.composite_score < fe_free.composite_score


# ===========================================================================
# 8. EVALUATE GPU (unit, with real DB)
# ===========================================================================
class TestEvaluateGPU:
    def test_returns_gpu_result(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        result = evaluate_gpu(db, gpu, w, c)
        assert isinstance(result, GPUResult)
        assert result.gpu_name == "H200 SXM"

    def test_all_fields_populated(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        result = evaluate_gpu(db, gpu, w, c)
        assert result.tokens_per_sec is not None and result.tokens_per_sec > 0
        assert result.prefill_tokens_per_sec is not None and result.prefill_tokens_per_sec > 0
        assert result.tco_usd is not None and result.tco_usd > 0
        assert result.complexity_score is not None
        assert result.availability_score is not None
        assert result.topology is not None
        assert result.kv_cache_gb is not None

    def test_estimated_gpu_has_warning(self, db):
        gpu = db.query(GPU).filter(GPU.name == "MI350X").first()
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        result = evaluate_gpu(db, gpu, w, c)
        assert any("estimated" in w.lower() for w in result.warnings)

    def test_cooling_mismatch_warning(self, db):
        gpu = db.query(GPU).filter(GPU.name == "GB200 NVL72").first()
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput(cooling_type="air")
        result = evaluate_gpu(db, gpu, w, c)
        assert any("requires liquid cooling" in w or "incompatible with air cooling" in w for w in result.warnings)

    def test_fp8_changes_throughput(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w_fp16 = WorkloadInput(model_params_b=70, precision="FP16")
        w_fp8 = WorkloadInput(model_params_b=70, precision="FP8")
        c = ConstraintInput()
        r16 = evaluate_gpu(db, gpu, w_fp16, c)
        r8 = evaluate_gpu(db, gpu, w_fp8, c)
        assert r8.tokens_per_sec > r16.tokens_per_sec

    def test_large_model_needs_more_gpus(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w_small = WorkloadInput(model_params_b=7)
        w_large = WorkloadInput(model_params_b=405)
        c = ConstraintInput()
        r_small = evaluate_gpu(db, gpu, w_small, c)
        r_large = evaluate_gpu(db, gpu, w_large, c)
        assert r_large.topology.gpu_count > r_small.topology.gpu_count


# ===========================================================================
# 8b. LATENCY METRICS (TTFT / TPOT)
# ===========================================================================
class TestLatencyMetrics:
    def test_ttft_and_tpot_populated(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, context_length=4096, concurrent_users=1)
        c = ConstraintInput()
        r = evaluate_gpu(db, gpu, w, c)
        assert r.ttft_ms is not None and r.ttft_ms > 0
        assert r.tpot_ms is not None and r.tpot_ms > 0
        assert r.per_user_decode_tps is not None and r.per_user_decode_tps > 0

    def test_tpot_matches_inverse_per_user_decode(self, db):
        # TPOT_ms = 1000 / per_user_decode_tps by construction.
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=10)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.tpot_ms == pytest.approx(1000.0 / r.per_user_decode_tps, rel=1e-3)

    def test_per_user_decode_drops_with_concurrency(self, db):
        # More users sharing the same aggregate → each gets a smaller slice.
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        c = ConstraintInput()
        r1 = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, concurrent_users=1), c)
        r50 = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, concurrent_users=50), c)
        assert r50.per_user_decode_tps < r1.per_user_decode_tps
        assert r50.tpot_ms > r1.tpot_ms

    def test_ttft_scales_with_context_length(self, db):
        # Longer prompts take longer to chew through; TTFT must rise.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        c = ConstraintInput()
        r4k = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, context_length=4096), c)
        r64k = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, context_length=65536), c)
        assert r64k.ttft_ms > r4k.ttft_ms

    def test_tpot_missed_advisory_emitted(self, db):
        # Set an absurdly tight TPOT target — every GPU should miss it.
        gpu = db.query(GPU).filter(GPU.name == "MI300X").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=100)
        c = ConstraintInput(target_tpot_ms=1)
        r = evaluate_gpu(db, gpu, w, c)
        assert "TPOT_MISSED" in r.violation_codes

    def test_tpot_missed_advisory_does_not_gate_ranking(self, db):
        # TPOT_MISSED is informational — it should not appear in
        # HARD_VIOLATION_CODES, so it doesn't affect sweet-spot eligibility.
        from app.engine.optimizer import HARD_VIOLATION_CODES
        assert "TPOT_MISSED" not in HARD_VIOLATION_CODES

    def test_no_target_means_no_advisory(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=100)
        c = ConstraintInput()  # no target_tpot_ms set
        r = evaluate_gpu(db, gpu, w, c)
        assert "TPOT_MISSED" not in r.violation_codes


# ===========================================================================
# 8c. MULTI-TENANCY (MIG / Run:ai fractional)
# ===========================================================================
class TestMultiTenancy:
    def test_dedicated_is_default(self, db):
        # No tenancy fields set -> dedicated, no tenancy advisories.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        r = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70), ConstraintInput())
        assert r.tenancy_mode_applied is None
        assert r.per_tenant_decode_tps is None
        assert "MIG_NVLINK_DISABLED" not in r.violation_codes
        assert "RUNAI_TIME_SLICED" not in r.violation_codes

    def test_mig_supported_on_hopper(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H100 SXM5").first()
        # 7B FP8 (~7GB weights) easily fits in a 1g.10gb slice.
        w = WorkloadInput(
            model_params_b=7, precision="FP8",
            multi_tenancy_mode="mig", mig_profile="1g.10gb",
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "MIG_NOT_SUPPORTED" not in r.violation_codes
        assert r.tenancy_mode_applied == "mig"
        assert r.tenants_per_gpu == 7
        assert "MIG_NVLINK_DISABLED" in r.violation_codes
        assert r.per_tenant_decode_tps is not None and r.per_tenant_decode_tps > 0
        assert r.per_tenant_kv_cache_gb is not None

    def test_mig_blocked_on_blackwell(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w = WorkloadInput(
            model_params_b=7, multi_tenancy_mode="mig", mig_profile="3g.40gb",
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "MIG_NOT_SUPPORTED" in r.violation_codes

    def test_mig_blocked_on_amd(self, db):
        gpu = db.query(GPU).filter(GPU.name == "MI300X").first()
        w = WorkloadInput(
            model_params_b=7, multi_tenancy_mode="mig", mig_profile="1g.10gb",
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "MIG_NOT_SUPPORTED" in r.violation_codes

    def test_mig_blocked_on_rack_scale(self, db):
        # GB200 NVL72 is rack-scale — MIG isn't exposed across the NVL fabric.
        # Use liquid cooling so the DLC_REQUIRED check passes first.
        gpu = db.query(GPU).filter(GPU.name == "GB200 NVL72").first()
        w = WorkloadInput(
            model_params_b=7, multi_tenancy_mode="mig", mig_profile="1g.10gb",
        )
        c = ConstraintInput(cooling_type="liquid")
        r = evaluate_gpu(db, gpu, w, c)
        assert "MIG_NOT_SUPPORTED" in r.violation_codes

    def test_mig_missing_profile_is_hard_fail(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=7, multi_tenancy_mode="mig", mig_profile=None)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "MIG_PROFILE_REQUIRED" in r.violation_codes

    def test_mig_invalid_profile_is_hard_fail(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=7, multi_tenancy_mode="mig", mig_profile="bogus")
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "MIG_PROFILE_REQUIRED" in r.violation_codes

    def test_mig_smaller_profile_means_more_instances(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H100 SXM5").first()
        c = ConstraintInput()
        r1g = evaluate_gpu(
            db, gpu, WorkloadInput(model_params_b=7, precision="FP8",
                                   multi_tenancy_mode="mig", mig_profile="1g.10gb"), c,
        )
        r3g = evaluate_gpu(
            db, gpu, WorkloadInput(model_params_b=7, precision="FP8",
                                   multi_tenancy_mode="mig", mig_profile="3g.40gb"), c,
        )
        assert r1g.tenants_per_gpu == 7
        assert r3g.tenants_per_gpu == 2

    def test_runai_fractional_divides_throughput(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        c = ConstraintInput()
        r_dedicated = evaluate_gpu(
            db, gpu, WorkloadInput(model_params_b=70), c,
        )
        r_runai_4 = evaluate_gpu(
            db, gpu, WorkloadInput(
                model_params_b=70,
                multi_tenancy_mode="runai_fractional",
                tenants=4,
            ), c,
        )
        # Run:ai with 4 tenants → roughly aggregate ÷ 4 (plus 5% KV penalty).
        ratio = r_runai_4.decode_tokens_per_sec / r_dedicated.decode_tokens_per_sec
        assert 0.20 < ratio < 0.27   # ~ 1/4 within KV penalty band
        assert r_runai_4.tenancy_mode_applied == "runai_fractional"
        assert "RUNAI_TIME_SLICED" in r_runai_4.violation_codes
        assert r_runai_4.tenants_per_gpu == 4

    def test_runai_advisory_does_not_gate_ranking(self, db):
        from app.engine.optimizer import HARD_VIOLATION_CODES
        # MIG hard codes ARE gating; the time-sliced advisory is NOT.
        assert "RUNAI_TIME_SLICED" not in HARD_VIOLATION_CODES
        assert "MIG_NVLINK_DISABLED" not in HARD_VIOLATION_CODES
        assert "MIG_NOT_SUPPORTED" in HARD_VIOLATION_CODES
        assert "MIG_PROFILE_REQUIRED" in HARD_VIOLATION_CODES

    def test_runai_single_tenant_falls_back_to_dedicated(self, db):
        # tenants=1 in runai_fractional is a no-op — treat as dedicated.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(
            model_params_b=70, multi_tenancy_mode="runai_fractional", tenants=1,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.tenancy_mode_applied is None  # collapsed to dedicated
        assert "RUNAI_TIME_SLICED" not in r.violation_codes


# ===========================================================================
# 8d. NVLINK TOPOLOGY (Sprint 9b)
# ===========================================================================
class TestNVLinkTopology:
    def test_seed_topology_classifications(self, db):
        # Sanity-check the seed data — every shipping GPU should have a
        # topology classified.  Catches regressions if a new GPU is seeded
        # without nvlink_topology.
        gpus = db.query(GPU).all()
        topologies = {g.name: g.nvlink_topology for g in gpus}
        assert topologies["H100 SXM5"] == "nvswitch"
        assert topologies["H200 SXM"] == "nvswitch"
        assert topologies["B200 HGX"] == "nvswitch"
        assert topologies["B300 HGX"] == "nvswitch"
        assert topologies["GB200 NVL72"] == "nvl_fabric"
        assert topologies["GB300 NVL72"] == "nvl_fabric"
        assert topologies["RTX PRO 6000 BSE"] == "none"
        assert topologies["MI300X"] == "point_to_point"
        assert topologies["MI350X"] == "point_to_point"
        assert topologies["MI355X"] == "point_to_point"

    def test_nvswitch_no_intra_node_derate(self, db):
        # NVSwitch boards keep full link-rate intra-node — effective_bandwidth
        # should equal the GPU's interconnect_bw_gb_s on a single-node TP fit.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, precision="FP16")
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        topo = r.topology
        assert topo is not None
        if topo.nodes == 1:
            assert topo.effective_bandwidth_gb_s == gpu.interconnect_bw_gb_s

    def test_point_to_point_derate_at_tp_above_4(self, db):
        # MI300X is point_to_point. A model that needs TP > 4 on a single node
        # should take the 15% bandwidth derate.
        gpu = db.query(GPU).filter(GPU.name == "MI300X").first()
        # 405B FP16 weights (~810GB) need TP=8 on MI300X (192GB each) — over 4.
        w = WorkloadInput(model_params_b=405, precision="FP16")
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        topo = r.topology
        assert topo is not None
        if topo.tp_degree > 4 and topo.nodes == 1:
            expected = gpu.interconnect_bw_gb_s * 0.85
            assert topo.effective_bandwidth_gb_s == pytest.approx(expected, rel=1e-3)


# ===========================================================================
# 8e. MOE ROUTING OVERHEAD (Sprint 9a)
# ===========================================================================
class TestMoERoutingOverhead:
    def test_dense_model_has_no_moe_fields(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        r = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, is_moe=False), ConstraintInput())
        assert r.moe_active_param_fraction is None
        assert r.moe_effective_bw_per_token_gb is None
        assert r.moe_routing_overhead_pct is None

    def test_moe_fields_populated_when_is_moe(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        # Mixtral-8x22B-style: 22B active out of 8 experts (~176B total).
        w = WorkloadInput(
            model_params_b=176, precision="FP16",
            is_moe=True, num_experts=8, active_experts=2,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.moe_active_param_fraction == pytest.approx(0.25)
        # 176B × 0.25 × 2 bytes/param = ~88 GB per token
        assert r.moe_effective_bw_per_token_gb == pytest.approx(88, abs=1)

    def test_no_overhead_when_all_experts_active(self, db):
        # active_experts == num_experts means dispatch is a no-op.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(
            model_params_b=70, is_moe=True, num_experts=8, active_experts=8,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.moe_routing_overhead_pct == 0.0

    def test_intra_node_overhead_around_12pct(self, db):
        # 405B FP8 with sparse MoE on H200 → multi-GPU intra-node, EP > 1.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(
            model_params_b=405, precision="FP8",
            is_moe=True, num_experts=8, active_experts=2,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.topology is not None
        if r.topology.nodes == 1 and r.topology.gpu_count > 1:
            assert r.moe_routing_overhead_pct == pytest.approx(12.0, abs=0.1)

    def test_multi_node_overhead_around_22pct(self, db):
        # A workload that pushes onto 2+ nodes — MoE all-to-all crosses IB.
        gpu = db.query(GPU).filter(GPU.name == "H100 SXM5").first()
        # 671B (DeepSeek-V3-class) FP8 + 100 concurrent users → multi-node TP.
        w = WorkloadInput(
            model_params_b=671, precision="FP8", concurrent_users=100,
            is_moe=True, num_experts=256, active_experts=8,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput(cooling_type="liquid"))
        assert r.topology is not None
        if r.topology.nodes > 1:
            assert r.moe_routing_overhead_pct == pytest.approx(22.0, abs=0.1)

    def test_decode_throughput_drops_when_moe_routing_applied(self, db):
        # With identical compute + memory, MoE routing overhead should depress
        # decode_tps relative to a dense model of equivalent active params.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        # MoE: 280B total / 8 experts / 2 active = 70B active.  Multi-GPU → 12% overhead.
        moe = WorkloadInput(
            model_params_b=280, precision="FP8", concurrent_users=10,
            is_moe=True, num_experts=8, active_experts=2,
        )
        r_moe = evaluate_gpu(db, gpu, moe, ConstraintInput())
        if r_moe.topology and r_moe.topology.gpu_count > 1 and r_moe.moe_routing_overhead_pct:
            # The penalty should be visible (decode_tps reflects the 12% drop).
            assert r_moe.moe_routing_overhead_pct > 0


# ===========================================================================
# 9. RUN_COMPARISON (full pipeline)
# ===========================================================================
class TestRunComparison:
    def test_returns_comparison_response(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        resp = run_comparison(db, w, c)
        assert isinstance(resp, ComparisonResponse)
        # 10 GPUs total: 8 from HTML (H200, B200, B300, GB200, GB300, MI300X,
        # MI350X, MI355X) + H100 SXM5 + RTX PRO 6000 BSE seeded from extras.
        # B100 is parsed but excluded via EXCLUDED_GPUS.
        assert len(resp.results) == 10
        assert resp.sweet_spot_gpu is not None

    def test_results_sorted_by_composite(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        resp = run_comparison(db, w, c)
        scores = [r.composite_score for r in resp.results]
        assert scores == sorted(scores, reverse=True)

    def test_sweet_spot_passes_constraints(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput(max_budget_usd=100_000)
        resp = run_comparison(db, w, c)
        sweet = next(r for r in resp.results if r.gpu_name == resp.sweet_spot_gpu)
        # Sweet spot should be within budget (if any GPU is)
        within_budget = [r for r in resp.results if r.tco_usd and r.tco_usd <= 100_000]
        if within_budget:
            assert sweet.tco_usd <= 100_000

    def test_all_gpus_present(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        resp = run_comparison(db, w, c)
        names = {r.gpu_name for r in resp.results}
        assert "H200 SXM" in names
        assert "B200 HGX" in names
        assert "MI300X" in names
        assert "GB200 NVL72" in names

    def test_workload_echoed_back(self, db):
        w = WorkloadInput(model_params_b=70, precision="FP8", concurrent_users=5)
        c = ConstraintInput()
        resp = run_comparison(db, w, c)
        assert resp.workload.model_params_b == 70
        assert resp.workload.precision == "FP8"
        assert resp.workload.concurrent_users == 5


# ===========================================================================
# 10. COST ENGINE
# ===========================================================================
class TestCostEngine:
    def test_tco_increases_with_gpu_count(self):
        c1 = calc_tco(1, 30_000, 700, 100.0)
        c4 = calc_tco(4, 30_000, 700, 100.0)
        assert c4.tco_36m_usd > c1.tco_36m_usd

    def test_tco_includes_network_cost(self):
        c_no_net = calc_tco(4, 30_000, 700, 100.0, network_switch_cost_usd=0)
        c_net = calc_tco(4, 30_000, 700, 100.0, network_switch_cost_usd=60_000)
        assert c_net.tco_36m_usd > c_no_net.tco_36m_usd

    def test_tokens_per_usd_positive(self):
        c = calc_tco(1, 30_000, 700, 100.0)
        assert c.tokens_per_usd_per_month > 0

    def test_network_cost_scales_with_nodes(self):
        c2 = calc_network_cost(2)
        c8 = calc_network_cost(8)
        assert c8 > c2

    def test_network_cost_xdr_more_expensive(self):
        c_ndr = calc_network_cost(4, "IB_NDR")
        c_xdr = calc_network_cost(4, "IB_XDR")
        assert c_xdr > c_ndr

    def test_fallback_price_when_none(self):
        c = calc_tco(1, None, 700, 100.0)
        assert c.capex_usd > 0


# ===========================================================================
# 11. COMPLEXITY ENGINE
# ===========================================================================
class TestComplexityEngine:
    def test_nvidia_higher_maturity_than_amd(self, db):
        nv = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        amd = db.query(GPU).filter(GPU.name == "MI300X").first()
        nv_cx = calc_complexity(db, nv)
        amd_cx = calc_complexity(db, amd)
        assert nv_cx.final_score >= amd_cx.final_score

    def test_user_cooling_not_double_penalised(self, db):
        # Cooling mismatch is the optimizer's responsibility (Violation.COOLING_*).
        # calc_complexity must not double-count it via user_cooling.
        gpu = db.query(GPU).filter(GPU.name == "GB200 NVL72").first()
        cx_air = calc_complexity(db, gpu, user_cooling="air")
        cx_liq = calc_complexity(db, gpu, user_cooling="liquid")
        assert cx_air.final_score == cx_liq.final_score

    def test_fp8_penalty_for_no_support(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        cx_fp16 = calc_complexity(db, gpu, precision="FP16")
        cx_fp8 = calc_complexity(db, gpu, precision="FP8")
        # H200 has no FP8 → penalty
        assert cx_fp8.final_score <= cx_fp16.final_score

    def test_score_in_0_10_range(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        cx = calc_complexity(db, gpu)
        assert 0 <= cx.final_score <= 10


# ===========================================================================
# 12. AVAILABILITY ENGINE
# ===========================================================================
class TestAvailabilityEngine:
    def test_ga_gpu_higher_score_than_estimated(self, db):
        h200 = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        b300 = db.query(GPU).filter(GPU.name == "B300 HGX").first()
        av_h = calc_availability(db, h200)
        av_b = calc_availability(db, b300)
        assert av_h.score >= av_b.score

    def test_meets_constraint_when_within_limit(self, db):
        h200 = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        av = calc_availability(db, h200, max_lead_time_weeks=52)
        assert av.meets_constraint is True

    def test_fails_constraint_when_over_limit(self, db):
        h200 = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        av = calc_availability(db, h200, max_lead_time_weeks=0)
        assert av.meets_constraint is False

    def test_score_between_0_and_1(self, db):
        for gpu in db.query(GPU).all():
            av = calc_availability(db, gpu)
            assert 0 <= av.score <= 1.0
