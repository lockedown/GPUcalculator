"""Core tests for the optimizer pipeline: rank normalisation, constraint
penalties, concurrent-users end-to-end behaviour, benchmark blending, the
weighted composite scoring, the ``evaluate_gpu`` happy-path smoke checks,
and the full ``run_comparison`` orchestration.

Per-feature tests (latency, multi-tenancy, NVLink topology, MoE routing,
disaggregation) live in ``test_evaluate_gpu_features.py``.
Calibration tests live in ``test_calibration.py``.
Topology unit tests (no DB) live in ``test_topology.py``.
"""

import pytest

from app.engine.optimizer import (
    _rank_normalize,
    _constraint_penalty,
    _passes_all_constraints,
    _benchmark_perf_score,
    _benchmark_scores_dict,
    normalize_and_rank,
    evaluate_gpu,
    run_calculation,
    run_comparison,
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
from app.models import GPU

from tests.conftest import mock_gpu as _mock_gpu


# ===========================================================================
# RANK NORMALIZATION
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
# CONSTRAINT PENALTIES
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
# CONCURRENT_USERS END-TO-END IMPACT
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
# BENCHMARK BLENDING
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
# NORMALIZE AND RANK
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
# EVALUATE GPU (unit, with real DB)
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
# RUN_COMPARISON (full pipeline)
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
# COST ENGINE
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
# COMPLEXITY ENGINE
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
# AVAILABILITY ENGINE
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
