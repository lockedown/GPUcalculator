"""Unit tests for the cost calculation engine."""

import pytest
from app.engine.cost import calc_tco, calc_network_cost


class TestTCO:
    def test_single_gpu_basic(self):
        result = calc_tco(
            gpu_count=1,
            gpu_price_usd=30000,
            tdp_watts=700,
            tokens_per_sec=34.0,
        )
        assert result.capex_usd == pytest.approx(30000, rel=0.01)
        assert result.opex_monthly_usd > 0
        assert result.tco_36m_usd > result.capex_usd
        assert result.power_kw == pytest.approx(0.7, rel=0.01)

    def test_multi_gpu_scales_capex(self):
        r1 = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        r8 = calc_tco(gpu_count=8, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=272)
        assert r8.capex_usd == pytest.approx(r1.capex_usd * 8, rel=0.01)

    def test_power_scales_with_gpu_count(self):
        r1 = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        r4 = calc_tco(gpu_count=4, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=136)
        assert r4.power_kw == pytest.approx(r1.power_kw * 4, rel=0.01)

    def test_tokens_per_usd_positive(self):
        result = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        assert result.tokens_per_usd_per_month > 0

    def test_nvl72_rack(self):
        result = calc_tco(
            gpu_count=72,
            gpu_price_usd=40000,
            tdp_watts=1200,
            tokens_per_sec=4000,
            network_switch_cost_usd=0,  # NVL72 fabric built-in
        )
        # 72 × $40k = $2.88M direct (no FX conversion now)
        assert result.capex_usd > 2_500_000
        assert result.power_kw == pytest.approx(86.4, rel=0.01)


class TestCarbonAccounting:
    """Carbon emissions surfaced from the same power draw used for the
    electricity OpEx line. PUE-adjusted (cooling overhead is real emissions).
    """

    def test_carbon_present_and_positive(self):
        r = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        assert r.carbon_kg_per_year is not None
        assert r.carbon_kg_per_year > 0

    def test_carbon_scales_with_gpu_count(self):
        r1 = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        r8 = calc_tco(gpu_count=8, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=272)
        assert r8.carbon_kg_per_year == pytest.approx(r1.carbon_kg_per_year * 8, rel=0.01)

    def test_carbon_scales_linearly_with_grid_intensity(self):
        # Halving the grid intensity should halve the kg/year (everything else
        # held constant).
        r_us = calc_tco(
            gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34,
            grid_carbon_intensity_g_kwh=380,
        )
        r_pnw = calc_tco(
            gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34,
            grid_carbon_intensity_g_kwh=190,  # half US-East
        )
        assert r_pnw.carbon_kg_per_year == pytest.approx(r_us.carbon_kg_per_year / 2, rel=0.01)

    def test_carbon_pue_adjusted(self):
        # Liquid cooling has a lower PUE (1.15) than air (1.40); same TDP →
        # liquid emits less carbon per year.
        liquid = calc_tco(
            gpu_count=1, gpu_price_usd=40000, tdp_watts=1000, tokens_per_sec=100,
            cooling_type="liquid",
        )
        air = calc_tco(
            gpu_count=1, gpu_price_usd=40000, tdp_watts=1000, tokens_per_sec=100,
            cooling_type="air",
        )
        assert liquid.carbon_kg_per_year < air.carbon_kg_per_year

    def test_carbon_us_east_realistic_magnitude(self):
        # Sanity check: 1× 700W GPU at PUE 1.40 on a 380 g/kWh grid →
        # 0.7 × 1.40 × 8760 × 380 / 1000 ≈ 3,261 kg CO₂/year.
        r = calc_tco(
            gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34,
            cooling_type="air",
            grid_carbon_intensity_g_kwh=380,
        )
        assert 3_000 < r.carbon_kg_per_year < 3_500


class TestNetworkCost:
    def test_single_node_zero(self):
        cost = calc_network_cost(1, "IB_NDR")
        assert cost == 5000

    def test_multi_node_spine(self):
        cost = calc_network_cost(8, "IB_NDR")
        # > 4 nodes → 2 ports each
        assert cost == 5000 * 16

    def test_xdr_more_expensive(self):
        ndr = calc_network_cost(4, "IB_NDR")
        xdr = calc_network_cost(4, "IB_XDR")
        assert xdr > ndr
