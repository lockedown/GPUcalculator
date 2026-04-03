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

    def test_fp8_multiplier_applied(self):
        fp16 = calibrate_decode("B200 HGX", 57.1, "FP16")
        fp8 = calibrate_decode("B200 HGX", 57.1, "FP8")
        mult = get_fp8_multiplier("B200 HGX")
        assert fp8 == pytest.approx(fp16 * mult, rel=0.01)

    def test_fp4_also_applies_fp8_mult(self):
        fp16 = calibrate_decode("B300 HGX", 100.0, "FP16")
        fp4 = calibrate_decode("B300 HGX", 100.0, "FP4")
        assert fp4 > fp16

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
    def _make_result(self, tco=100_000, warnings=None, power_kw=5.0):
        r = GPUResult(
            gpu_id=1, gpu_name="Test", gpu_vendor="NVIDIA",
            tco_gbp=tco, warnings=warnings or [],
        )
        r._power_kw = power_kw  # type: ignore[attr-defined]
        return r

    def test_no_violations_no_penalty(self):
        r = self._make_result()
        c = ConstraintInput()
        assert _constraint_penalty(r, c) == 0.0

    def test_budget_violation_penalty(self):
        r = self._make_result(tco=200_000)
        c = ConstraintInput(max_budget_gbp=100_000)
        assert _constraint_penalty(r, c) > 0

    def test_budget_overshoot_scales_penalty(self):
        r_small = self._make_result(tco=120_000)
        r_big = self._make_result(tco=500_000)
        c = ConstraintInput(max_budget_gbp=100_000)
        assert _constraint_penalty(r_big, c) > _constraint_penalty(r_small, c)

    def test_power_violation_penalty(self):
        r = self._make_result(power_kw=50.0)
        c = ConstraintInput(max_power_per_rack_kw=40.0)
        assert _constraint_penalty(r, c) > 0

    def test_power_within_limit_no_penalty(self):
        r = self._make_result(power_kw=30.0)
        c = ConstraintInput(max_power_per_rack_kw=40.0)
        assert _constraint_penalty(r, c) == 0.0

    def test_lead_time_violation_penalty(self):
        r = self._make_result(warnings=["GPU lead time (20w) exceeds constraint"])
        r.availability_score = 0.3
        c = ConstraintInput(max_lead_time_weeks=8)
        assert _constraint_penalty(r, c) > 0

    def test_cooling_soft_penalty(self):
        r = self._make_result(warnings=["Test requires liquid cooling"])
        c = ConstraintInput()
        assert _constraint_penalty(r, c) == pytest.approx(0.10)

    def test_multiple_violations_stack(self):
        r = self._make_result(
            tco=200_000,
            warnings=["requires liquid cooling"],
            power_kw=100.0,
        )
        c = ConstraintInput(max_budget_gbp=100_000, max_power_per_rack_kw=40.0)
        penalty = _constraint_penalty(r, c)
        # Budget + power + cooling = should be > any single penalty
        assert penalty > 0.30

    def test_penalty_caps_at_0_9(self):
        r = self._make_result(
            tco=10_000_000,
            warnings=["lead time (52w) exceeds constraint", "requires liquid cooling"],
            power_kw=200.0,
        )
        r.availability_score = 0.1
        c = ConstraintInput(max_budget_gbp=100, max_power_per_rack_kw=10, max_lead_time_weeks=4)
        assert _constraint_penalty(r, c) <= 0.9

    def test_passes_all_no_constraints(self):
        r = self._make_result()
        c = ConstraintInput()
        assert _passes_all_constraints(r, c) is True

    def test_fails_budget_constraint(self):
        r = self._make_result(tco=200_000)
        c = ConstraintInput(max_budget_gbp=100_000)
        assert _passes_all_constraints(r, c) is False

    def test_fails_power_constraint(self):
        r = self._make_result(power_kw=100.0)
        c = ConstraintInput(max_power_per_rack_kw=40.0)
        assert _passes_all_constraints(r, c) is False

    def test_fails_lead_time_constraint(self):
        r = self._make_result(warnings=["GPU lead time (30w) exceeds constraint"])
        c = ConstraintInput(max_lead_time_weeks=12)
        assert _passes_all_constraints(r, c) is False

    def test_passes_within_all_limits(self):
        r = self._make_result(tco=50_000, power_kw=5.0)
        r.availability_score = 0.8
        c = ConstraintInput(max_budget_gbp=100_000, max_power_per_rack_kw=40.0, max_lead_time_weeks=12)
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
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=64, batch_size=1)
        assert topo.dp_degree == 8  # ceil(64/8) = 8, capped

    def test_dp_capped_at_8(self):
        gpu = _mock_gpu()
        topo = calc_topology(gpu, 14.0, 20.0, concurrent_users=1000, batch_size=1)
        assert topo.dp_degree <= 8

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
        assert b50.tco_gbp > b1.tco_gbp

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
        # GPUs filtered out by constraints (e.g. DLC-only) have no benchmark_scores
        evaluated = [r for r in results if r.tokens_per_sec is not None]
        assert len(evaluated) > 0
        for r in evaluated:
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
                tokens_per_sec=tps, tco_gbp=tco,
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
        results = self._make_results()
        c_no_budget = ConstraintInput()
        c_budget = ConstraintInput(max_budget_gbp=80_000)
        ranked_free = normalize_and_rank(
            [GPUResult(**r.model_dump()) for r in self._make_results()],
            c_no_budget.metric_weights, c_no_budget,
        )
        ranked_budget = normalize_and_rank(
            [GPUResult(**r.model_dump()) for r in self._make_results()],
            c_budget.metric_weights, c_budget,
        )
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
        assert result.tco_gbp is not None and result.tco_gbp > 0
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
# 9. RUN_COMPARISON (full pipeline)
# ===========================================================================
class TestRunComparison:
    def test_returns_comparison_response(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        resp = run_comparison(db, w, c)
        assert isinstance(resp, ComparisonResponse)
        assert len(resp.results) == 9
        assert resp.sweet_spot_gpu is not None

    def test_results_sorted_by_composite(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput()
        resp = run_comparison(db, w, c)
        scores = [r.composite_score for r in resp.results]
        assert scores == sorted(scores, reverse=True)

    def test_sweet_spot_passes_constraints(self, db):
        w = WorkloadInput(model_params_b=70)
        c = ConstraintInput(max_budget_gbp=100_000)
        resp = run_comparison(db, w, c)
        sweet = next(r for r in resp.results if r.gpu_name == resp.sweet_spot_gpu)
        # Sweet spot should be within budget (if any GPU is)
        within_budget = [r for r in resp.results if r.tco_gbp and r.tco_gbp <= 100_000]
        if within_budget:
            assert sweet.tco_gbp <= 100_000

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
        assert c4.tco_36m_gbp > c1.tco_36m_gbp

    def test_tco_includes_network_cost(self):
        c_no_net = calc_tco(4, 30_000, 700, 100.0, network_switch_cost_usd=0)
        c_net = calc_tco(4, 30_000, 700, 100.0, network_switch_cost_usd=60_000)
        assert c_net.tco_36m_gbp > c_no_net.tco_36m_gbp

    def test_tokens_per_gbp_positive(self):
        c = calc_tco(1, 30_000, 700, 100.0)
        assert c.tokens_per_gbp_per_month > 0

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
        assert c.capex_gbp > 0


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

    def test_cooling_penalty_applied(self, db):
        gpu = db.query(GPU).filter(GPU.name == "GB200 NVL72").first()
        if gpu.cooling_type == "liquid":
            cx_air = calc_complexity(db, gpu, user_cooling="air")
            cx_liq = calc_complexity(db, gpu, user_cooling="liquid")
            assert cx_air.final_score < cx_liq.final_score

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
