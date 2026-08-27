"""Tests for ``calc_topology`` — GPU-count, parallelism strategy, DP scaling,
rack-scale (NVL72), and PCIe path. No DB required; uses the ``mock_gpu``
helper from conftest.
"""

from app.engine.optimizer import calc_topology

from tests.conftest import mock_gpu as _mock_gpu


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
        # total_memory exceeds one rack's capacity → single-rack strategy label
        # no longer applies (multi-rack DP scaling kicks in instead — see
        # TestRackScaleMultiRack below).
        total_hbm = 192 * 72  # 13,824 GB
        topo = calc_topology(gpu, 100.0, total_hbm + 1)
        assert topo.parallelism_strategy != "NVL72 unified fabric"


class TestRackScaleMultiRack:
    """Rack-scale GPUs (NVL72 / Helios) are bought/deployed in whole-rack
    units — a workload that exceeds one rack's memory OR throughput must
    scale to multiple racks (DP across racks), not silently stay pinned at
    exactly one rack regardless of load. Added after finding real production
    scenarios (500 concurrent users, 405B model) where GB200/GB300/MI455X all
    reported a flat 72 GPUs / ~$5-8M TCO — as if one rack could serve any
    load — while non-rack GPUs correctly scaled to thousands of GPUs and
    hundreds of millions in TCO for the identical workload.
    """

    def test_scales_to_multiple_racks_when_memory_exceeds_one_rack(self):
        gpu = _mock_gpu(hbm_capacity_gb=192, is_rack_scale=True, rack_gpu_count=72)
        total_hbm = 192 * 72
        topo = calc_topology(gpu, 100.0, total_hbm * 2.5)  # needs 3 racks by memory
        assert topo.dp_degree == 3
        assert topo.gpu_count == 72 * 3
        assert topo.nodes == 3
        assert "3 racks" in topo.parallelism_strategy

    def test_scales_to_multiple_racks_when_throughput_insufficient(self):
        gpu = _mock_gpu(hbm_capacity_gb=192, is_rack_scale=True, rack_gpu_count=72)
        # Memory fits one rack, but 1000 users at MIN_DECODE_TPS_PER_USER=10
        # need 10,000 tok/s aggregate — far more than a tiny per-rack figure.
        topo = calc_topology(
            gpu, 100.0, 500.0,
            concurrent_users=1000, batch_size=1,
            per_gpu_decode_tps=5.0,  # calibrated whole-rack single-stream decode
        )
        assert topo.dp_degree > 1
        assert topo.gpu_count == 72 * topo.dp_degree

    def test_single_rack_still_returned_when_sufficient(self):
        # Regression guard: small workload on a rack-scale GPU should still
        # get the simple single-rack label, not multi-rack DP unnecessarily.
        gpu = _mock_gpu(hbm_capacity_gb=192, is_rack_scale=True, rack_gpu_count=72)
        topo = calc_topology(
            gpu, 100.0, 500.0,
            concurrent_users=1, batch_size=1,
            per_gpu_decode_tps=1000.0,
        )
        assert topo.dp_degree == 1
        assert topo.gpu_count == 72
        assert topo.parallelism_strategy == "NVL72 unified fabric"

    def test_tco_scales_with_rack_count(self):
        # The real-world symptom this fixed: TCO must grow with rack count,
        # not stay pinned near a single rack's price regardless of load.
        from app.engine.cost import calc_tco

        gpu = _mock_gpu(hbm_capacity_gb=192, is_rack_scale=True, rack_gpu_count=72)
        topo_1 = calc_topology(gpu, 100.0, 500.0, per_gpu_decode_tps=1000.0)
        topo_5 = calc_topology(
            gpu, 100.0, 500.0,
            concurrent_users=5000, batch_size=1, per_gpu_decode_tps=5.0,
        )
        assert topo_5.dp_degree > topo_1.dp_degree
        tco_1 = calc_tco(gpu_count=topo_1.gpu_count, gpu_price_usd=50_000, tdp_watts=1200, tokens_per_sec=100)
        tco_5 = calc_tco(gpu_count=topo_5.gpu_count, gpu_price_usd=50_000, tdp_watts=1200, tokens_per_sec=100)
        assert tco_5.tco_36m_usd > tco_1.tco_36m_usd * 2

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
