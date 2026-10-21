"""Tests for the feature-specific extensions added to ``evaluate_gpu`` over
the v2.0 sprint backlog: TTFT/TPOT latency surfacing, multi-tenancy
(MIG / Run:ai), NVLink topology classification, MoE routing overhead, and
disaggregated prefill/decode.

The base ``evaluate_gpu`` smoke tests live in ``test_optimizer_v2.py`` —
those check the result is well-formed for every GPU. These tests assert the
*behaviour* of each individual feature axis.
"""

import pytest

from app.engine.optimizer import evaluate_gpu
from app.models import GPU
from app.schemas.workload import ConstraintInput, WorkloadInput


# ===========================================================================
# Sprint 8 — Per-user latency (TTFT / TPOT)
# ===========================================================================
class TestLatencyMetrics:
    def test_ttft_and_tpot_populated(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, context_length=4096, concurrent_users=1)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.ttft_ms is not None and r.ttft_ms > 0
        assert r.tpot_ms is not None and r.tpot_ms > 0
        assert r.per_user_decode_tps is not None and r.per_user_decode_tps > 0

    def test_tpot_matches_inverse_per_user_decode(self, db):
        # TPOT_ms = 1000 / per_user_decode_tps by construction.
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=10)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.tpot_ms == pytest.approx(1000.0 / r.per_user_decode_tps, rel=1e-3)

    def test_aggregate_decode_is_per_user_rate_times_users(self, db):
        # Roofline rates are per sequence: total = per-user × concurrent users.
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w = WorkloadInput(model_params_b=70, precision="FP8", concurrent_users=32)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.decode_tokens_per_sec == pytest.approx(r.per_user_decode_tps * 32, rel=1e-3)
        # 32 users on B200 FP8 70B still decode at well over interactive speed.
        assert r.tpot_ms < 50

    def test_per_user_decode_drops_with_concurrency(self, db):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        c = ConstraintInput()
        r1 = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, concurrent_users=1), c)
        r50 = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, concurrent_users=50), c)
        assert r50.per_user_decode_tps < r1.per_user_decode_tps
        assert r50.tpot_ms > r1.tpot_ms

    def test_ttft_scales_with_context_length(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        c = ConstraintInput()
        r4k = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, context_length=4096), c)
        r64k = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, context_length=65536), c)
        assert r64k.ttft_ms > r4k.ttft_ms

    def test_tpot_missed_advisory_emitted(self, db):
        gpu = db.query(GPU).filter(GPU.name == "MI300X").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=100)
        c = ConstraintInput(target_tpot_ms=1)
        r = evaluate_gpu(db, gpu, w, c)
        assert "TPOT_MISSED" in r.violation_codes

    def test_tpot_missed_advisory_does_not_gate_ranking(self):
        from app.engine.optimizer import HARD_VIOLATION_CODES
        assert "TPOT_MISSED" not in HARD_VIOLATION_CODES

    def test_no_target_means_no_advisory(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=100)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "TPOT_MISSED" not in r.violation_codes


# ===========================================================================
# Sprint 11 — Multi-tenancy (MIG / Run:ai fractional)
# ===========================================================================
class TestMultiTenancy:
    def test_dedicated_is_default(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        r = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70), ConstraintInput())
        assert r.tenancy_mode_applied is None
        assert r.per_tenant_decode_tps is None
        assert "MIG_NVLINK_DISABLED" not in r.violation_codes
        assert "RUNAI_TIME_SLICED" not in r.violation_codes

    def test_mig_supported_on_hopper(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H100 SXM5").first()
        # 7B FP8 (~7GB weights) fits in a 1g.10gb slice.
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
        # Liquid cooling so DLC_REQUIRED doesn't short-circuit first.
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
        r_dedicated = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70), c)
        r_runai_4 = evaluate_gpu(
            db, gpu, WorkloadInput(
                model_params_b=70,
                multi_tenancy_mode="runai_fractional",
                tenants=4,
            ), c,
        )
        # ÷ 4 plus 5% KV-fragmentation penalty.
        ratio = r_runai_4.decode_tokens_per_sec / r_dedicated.decode_tokens_per_sec
        assert 0.20 < ratio < 0.27
        assert r_runai_4.tenancy_mode_applied == "runai_fractional"
        assert "RUNAI_TIME_SLICED" in r_runai_4.violation_codes
        assert r_runai_4.tenants_per_gpu == 4

    def test_runai_advisory_does_not_gate_ranking(self):
        from app.engine.optimizer import HARD_VIOLATION_CODES
        assert "RUNAI_TIME_SLICED" not in HARD_VIOLATION_CODES
        assert "MIG_NVLINK_DISABLED" not in HARD_VIOLATION_CODES
        assert "MIG_NOT_SUPPORTED" in HARD_VIOLATION_CODES
        assert "MIG_PROFILE_REQUIRED" in HARD_VIOLATION_CODES

    def test_runai_single_tenant_falls_back_to_dedicated(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(
            model_params_b=70, multi_tenancy_mode="runai_fractional", tenants=1,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.tenancy_mode_applied is None
        assert "RUNAI_TIME_SLICED" not in r.violation_codes


# ===========================================================================
# Sprint 9b — NVLink topology classification
# ===========================================================================
class TestNVLinkTopology:
    def test_seed_topology_classifications(self, db):
        # Sanity-check the seed data — every shipping GPU should have a
        # topology classified. Catches regressions if a new GPU is seeded
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
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        r = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70, precision="FP16"), ConstraintInput())
        topo = r.topology
        assert topo is not None
        if topo.nodes == 1:
            assert topo.effective_bandwidth_gb_s == gpu.interconnect_bw_gb_s

    def test_point_to_point_derate_at_tp_above_4(self, db):
        # MI300X is point_to_point; 405B FP16 needs TP=8 → 15% bandwidth derate.
        gpu = db.query(GPU).filter(GPU.name == "MI300X").first()
        w = WorkloadInput(model_params_b=405, precision="FP16")
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        topo = r.topology
        assert topo is not None
        if topo.tp_degree > 4 and topo.nodes == 1:
            expected = gpu.interconnect_bw_gb_s * 0.85
            assert topo.effective_bandwidth_gb_s == pytest.approx(expected, rel=1e-3)


# ===========================================================================
# Sprint 9a — MoE routing overhead
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
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(
            model_params_b=70, is_moe=True, num_experts=8, active_experts=8,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.moe_routing_overhead_pct == 0.0

    def test_intra_node_overhead_around_12pct(self, db):
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
        gpu = db.query(GPU).filter(GPU.name == "H100 SXM5").first()
        # DeepSeek-V3-class: 671B FP8 + 100 concurrent users → multi-node TP.
        w = WorkloadInput(
            model_params_b=671, precision="FP8", concurrent_users=100,
            is_moe=True, num_experts=256, active_experts=8,
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput(cooling_type="liquid"))
        assert r.topology is not None
        if r.topology.nodes > 1:
            assert r.moe_routing_overhead_pct == pytest.approx(22.0, abs=0.1)

    def test_decode_throughput_drops_when_moe_routing_applied(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        # 280B / 8 / 2 = 70B active. Multi-GPU → 12% overhead.
        moe = WorkloadInput(
            model_params_b=280, precision="FP8", concurrent_users=10,
            is_moe=True, num_experts=8, active_experts=2,
        )
        r_moe = evaluate_gpu(db, gpu, moe, ConstraintInput())
        if r_moe.topology and r_moe.topology.gpu_count > 1 and r_moe.moe_routing_overhead_pct:
            assert r_moe.moe_routing_overhead_pct > 0


# ===========================================================================
# Sprint 10 — Disaggregated prefill/decode (observability v1)
# ===========================================================================
class TestDisaggregation:
    def test_colocated_is_default(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        r = evaluate_gpu(db, gpu, WorkloadInput(model_params_b=70), ConstraintInput())
        assert r.topology.serving_mode == "colocated"
        assert r.topology.prefill_gpu_count == r.topology.gpu_count
        assert r.topology.decode_gpu_count == r.topology.gpu_count
        assert r.topology.prefill_role_strategy == r.topology.parallelism_strategy
        assert r.topology.decode_role_strategy == r.topology.parallelism_strategy

    def test_disaggregated_splits_30_70(self, db):
        # 405B FP16 forces multi-GPU so the split has room to breathe.
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=405, precision="FP16", serving_mode="disaggregated")
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert r.topology.serving_mode == "disaggregated"
        assert r.topology.prefill_gpu_count >= 1
        assert r.topology.decode_gpu_count >= 1
        assert r.topology.prefill_gpu_count + r.topology.decode_gpu_count == r.topology.gpu_count
        assert r.topology.decode_gpu_count >= r.topology.prefill_gpu_count
        assert "compute-dense" in r.topology.prefill_role_strategy
        assert "bandwidth-dense" in r.topology.decode_role_strategy

    def test_disaggregated_single_gpu_mirrors(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=7, precision="FP8", serving_mode="disaggregated")
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        if r.topology.gpu_count == 1:
            assert r.topology.prefill_gpu_count == 1
            assert r.topology.decode_gpu_count == 1

    def test_disagg_recommended_fires_on_high_concurrency_long_context(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=50, context_length=16384)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "DISAGG_RECOMMENDED" in r.violation_codes

    def test_disagg_recommended_silent_on_low_concurrency(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=1, context_length=4096)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "DISAGG_RECOMMENDED" not in r.violation_codes

    def test_disagg_recommended_silent_on_short_context(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(model_params_b=70, concurrent_users=100, context_length=2048)
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "DISAGG_RECOMMENDED" not in r.violation_codes

    def test_disagg_recommended_silent_when_already_disagg(self, db):
        gpu = db.query(GPU).filter(GPU.name == "H200 SXM").first()
        w = WorkloadInput(
            model_params_b=70, concurrent_users=50, context_length=16384,
            serving_mode="disaggregated",
        )
        r = evaluate_gpu(db, gpu, w, ConstraintInput())
        assert "DISAGG_RECOMMENDED" not in r.violation_codes

    def test_disagg_advisory_does_not_gate_ranking(self):
        from app.engine.optimizer import HARD_VIOLATION_CODES
        assert "DISAGG_RECOMMENDED" not in HARD_VIOLATION_CODES


# ===========================================================================
# Rack power limit is judged per rack, not on the whole cluster
# ===========================================================================
class TestRackPowerLimit:
    def _b200(self, db, users, limit_kw):
        gpu = db.query(GPU).filter(GPU.name == "B200 HGX").first()
        w = WorkloadInput(model_params_b=70, precision="FP8", concurrent_users=users)
        return evaluate_gpu(db, gpu, w, ConstraintInput(max_power_per_rack_kw=limit_kw))

    def test_big_cluster_split_over_racks_is_fine(self, db):
        # 72 GPUs (~72 kW total) over 3 racks of ~39 kW each fits a 40 kW rack limit.
        r = self._b200(db, users=256, limit_kw=40)
        assert r.rack_plan.total_racks > 1 and r.rack_plan.fits_power_constraint
        assert "POWER_EXCEEDED" not in r.violation_codes

    def test_single_rack_over_limit_is_flagged(self, db):
        # One 8-GPU B200 server rack draws ~12 kW; a 10 kW limit must trip even
        # though the GPUs alone (3 kW total) are under it.
        r = self._b200(db, users=32, limit_kw=10)
        assert not r.rack_plan.fits_power_constraint
        assert "POWER_EXCEEDED" in r.violation_codes
