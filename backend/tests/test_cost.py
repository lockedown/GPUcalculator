"""Unit tests for the cost calculation engine."""

import pytest
from app.engine.cost import calc_tco, calc_network_cost, GBP_PER_USD


class TestTCO:
    def test_single_gpu_basic(self):
        result = calc_tco(
            gpu_count=1,
            gpu_price_usd=30000,
            tdp_watts=700,
            tokens_per_sec=34.0,
        )
        assert result.capex_gbp == pytest.approx(30000 * GBP_PER_USD, rel=0.01)
        assert result.opex_monthly_gbp > 0
        assert result.tco_36m_gbp > result.capex_gbp
        assert result.power_kw == pytest.approx(0.7, rel=0.01)

    def test_multi_gpu_scales_capex(self):
        r1 = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        r8 = calc_tco(gpu_count=8, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=272)
        assert r8.capex_gbp == pytest.approx(r1.capex_gbp * 8, rel=0.01)

    def test_power_scales_with_gpu_count(self):
        r1 = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        r4 = calc_tco(gpu_count=4, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=136)
        assert r4.power_kw == pytest.approx(r1.power_kw * 4, rel=0.01)

    def test_tokens_per_gbp_positive(self):
        result = calc_tco(gpu_count=1, gpu_price_usd=30000, tdp_watts=700, tokens_per_sec=34)
        assert result.tokens_per_gbp_per_month > 0

    def test_nvl72_rack(self):
        result = calc_tco(
            gpu_count=72,
            gpu_price_usd=40000,
            tdp_watts=1200,
            tokens_per_sec=4000,
            network_switch_cost_usd=0,  # NVL72 fabric built-in
        )
        assert result.capex_gbp > 2_000_000
        assert result.power_kw == pytest.approx(86.4, rel=0.01)


class TestNetworkCost:
    def test_single_node_zero(self):
        cost = calc_network_cost(1, "IB_NDR")
        assert cost == 15000

    def test_multi_node_spine(self):
        cost = calc_network_cost(8, "IB_NDR")
        # > 4 nodes → 2 ports each
        assert cost == 15000 * 16

    def test_xdr_more_expensive(self):
        ndr = calc_network_cost(4, "IB_NDR")
        xdr = calc_network_cost(4, "IB_XDR")
        assert xdr > ndr
