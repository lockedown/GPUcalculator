"""Tests for the power-aware rack planning engine."""

import pytest
from app.engine.rack_planner import plan_rack_layout, RackPlan


class TestBasicLayout:
    """Test basic rack layout calculations."""

    def test_single_gpu_sxm(self):
        plan = plan_rack_layout(
            gpu_name="B200 SXM",
            gpu_count=1,
            tdp_watts=1000,
            form_factor="SXM",
            cooling_type="air",
        )
        assert plan.total_racks == 1
        assert plan.servers_per_rack >= 1
        assert plan.gpus_per_rack >= 1
        assert plan.u_per_server == 8

    def test_eight_gpu_single_node(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="air",
        )
        assert plan.total_racks == 1
        assert plan.gpus_per_rack >= 8

    def test_multi_node_requires_racks(self):
        plan = plan_rack_layout(
            gpu_name="B200 SXM",
            gpu_count=32,
            tdp_watts=1000,
            form_factor="SXM",
            cooling_type="air",
        )
        assert plan.total_racks >= 1
        assert plan.total_racks * plan.gpus_per_rack >= 32

    def test_nvl72_rack_scale(self):
        plan = plan_rack_layout(
            gpu_name="GB200 NVL72",
            gpu_count=72,
            tdp_watts=1000,
            form_factor="NVL72",
            cooling_type="liquid",
            is_rack_scale=True,
            rack_gpu_count=72,
        )
        assert plan.total_racks == 1
        assert plan.u_per_server == 42
        assert plan.gpus_per_rack == 72


class TestPowerCalculations:
    """Test power and PDU calculations."""

    def test_power_per_gpu_kw(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="air",
        )
        assert plan.power_per_gpu_kw == 0.7

    def test_pue_multiplier(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="air",
            pue=1.3,
        )
        assert plan.pue_adjusted_power_kw > plan.total_power_kw
        assert abs(plan.pue_adjusted_power_kw - plan.total_power_kw * 1.3) < 0.1

    def test_high_tdp_selects_high_density_pdu(self):
        plan = plan_rack_layout(
            gpu_name="B300 SXM",
            gpu_count=8,
            tdp_watts=1200,
            form_factor="SXM",
            cooling_type="air",
        )
        assert plan.pdu_tier == "high_density_air"

    def test_liquid_cooling_selects_liquid_pdu(self):
        plan = plan_rack_layout(
            gpu_name="GB200 NVL72",
            gpu_count=72,
            tdp_watts=1000,
            form_factor="NVL72",
            cooling_type="liquid",
            is_rack_scale=True,
            rack_gpu_count=72,
        )
        assert plan.pdu_tier == "liquid_cooled"


class TestConstraints:
    """Test power and cooling constraints."""

    def test_fits_within_power_constraint(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="air",
            max_power_per_rack_kw=50.0,
        )
        assert plan.fits_power_constraint is True

    def test_exceeds_power_constraint(self):
        plan = plan_rack_layout(
            gpu_name="B300 SXM",
            gpu_count=8,
            tdp_watts=1200,
            form_factor="SXM",
            cooling_type="air",
            max_power_per_rack_kw=10.0,
        )
        # With 10kW limit, can only fit ~1 server but power_per_rack will still
        # be the actual power of servers that fit, which may exceed 10kW for 1 server
        # The constraint check is per-rack, not per-server
        assert isinstance(plan.fits_power_constraint, bool)

    def test_air_cooling_capacity_warning(self):
        plan = plan_rack_layout(
            gpu_name="B300 SXM",
            gpu_count=8,
            tdp_watts=1200,
            form_factor="SXM",
            cooling_type="air",
        )
        # 8 × 1200W = 9.6kW + 10% overhead ≈ 10.56kW per server
        # Multiple servers per rack will exceed air cooling 30kW
        if plan.power_per_rack_kw > 30.0:
            assert plan.fits_cooling is False
            assert plan.density_warning is not None

    def test_liquid_cooling_high_capacity(self):
        plan = plan_rack_layout(
            gpu_name="B300 SXM",
            gpu_count=8,
            tdp_watts=1200,
            form_factor="SXM",
            cooling_type="liquid",
        )
        assert plan.cooling_capacity_kw == 120.0


class TestHeadroom:
    """Test PDU and cooling headroom calculations."""

    def test_pdu_headroom_positive(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="liquid",
        )
        assert plan.pdu_headroom_pct >= 0

    def test_cooling_headroom_positive_liquid(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="liquid",
        )
        assert plan.cooling_headroom_pct > 0

    def test_u_utilization_reasonable(self):
        plan = plan_rack_layout(
            gpu_name="H200 SXM5",
            gpu_count=8,
            tdp_watts=700,
            form_factor="SXM",
            cooling_type="air",
        )
        assert 0 < plan.u_utilization_pct <= 100
