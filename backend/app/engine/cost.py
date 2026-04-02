"""TCO calculation engine — CapEx + OpEx over 36 months."""

from dataclasses import dataclass

# Defaults
DEFAULT_PUE = 1.3
DEFAULT_COST_PER_KWH_GBP = 0.15
DEFAULT_HOURS_PER_MONTH = 730
DEFAULT_AMORTIZATION_MONTHS = 36
GBP_PER_USD = 0.79  # Approximate conversion


@dataclass
class CostResult:
    capex_gbp: float
    opex_monthly_gbp: float
    tco_36m_gbp: float
    tokens_per_gbp_per_month: float
    power_kw: float


def calc_tco(
    gpu_count: int,
    gpu_price_usd: float | None,
    tdp_watts: int | None,
    tokens_per_sec: float,
    network_switch_cost_usd: float = 0.0,
    storage_cost_usd: float = 0.0,
    pue: float = DEFAULT_PUE,
    cost_per_kwh_gbp: float = DEFAULT_COST_PER_KWH_GBP,
    amortization_months: int = DEFAULT_AMORTIZATION_MONTHS,
) -> CostResult:
    """
    Calculate Total Cost of Ownership.

    CapEx = (gpu_price × gpu_count) + network_switch_cost + storage_cost
    OpEx_monthly = (total_tdp_kw × PUE × hours_per_month × cost_per_kwh)
    TCO = CapEx + (OpEx_monthly × amortization_months)
    """
    # CapEx
    if gpu_price_usd is None:
        gpu_price_usd = estimate_gpu_price(gpu_count)

    capex_usd = (gpu_price_usd * gpu_count) + network_switch_cost_usd + storage_cost_usd
    capex_gbp = capex_usd * GBP_PER_USD

    # OpEx (power)
    if tdp_watts is None:
        tdp_watts = 700  # Conservative default

    total_power_kw = (tdp_watts * gpu_count) / 1000.0
    effective_power_kw = total_power_kw * pue
    opex_monthly = effective_power_kw * DEFAULT_HOURS_PER_MONTH * cost_per_kwh_gbp

    # TCO
    tco = capex_gbp + (opex_monthly * amortization_months)

    # Tokens per £
    tokens_per_month = tokens_per_sec * 3600 * 24 * 30  # Assume continuous operation
    monthly_cost = tco / amortization_months
    tokens_per_gbp = tokens_per_month / monthly_cost if monthly_cost > 0 else 0

    return CostResult(
        capex_gbp=capex_gbp,
        opex_monthly_gbp=opex_monthly,
        tco_36m_gbp=tco,
        tokens_per_gbp_per_month=tokens_per_gbp,
        power_kw=total_power_kw,
    )


def estimate_gpu_price(gpu_count: int) -> float:
    """Fallback price estimate if MSRP not available."""
    return 25000.0  # Conservative estimate per GPU in USD


def calc_network_cost(nodes: int, switch_type: str = "IB_NDR") -> float:
    """Estimate network switch costs based on node count and switch type."""
    switch_costs = {
        "IB_NDR": 15000,   # Per port, ~$15k per 400G port
        "IB_XDR": 25000,   # Per port, ~$25k per 800G port
        "RoCEv2": 8000,    # Per port
        "Ethernet_400G": 5000,
    }
    cost_per_port = switch_costs.get(switch_type, 15000)
    # Each node needs at least 1 uplink; add spine switches for >4 nodes
    ports_needed = nodes
    if nodes > 4:
        ports_needed = nodes * 2  # Leaf + spine
    return cost_per_port * ports_needed
