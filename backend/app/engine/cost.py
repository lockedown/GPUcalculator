"""TCO calculation engine — CapEx + OpEx over 36 months, denominated in USD."""

from dataclasses import dataclass

# Defaults — refreshed against 2026 market data.
# PUE: Uptime Institute 2025 industry average is 1.54 for legacy enterprise;
# direct-liquid-cooled GPU pods (NVL72-class) achieve ~1.10–1.15.
PUE_LIQUID = 1.15
PUE_AIR = 1.40  # Uptime 2025 industry avg is 1.54; 1.40 is the modern AI-focused air bracket
DEFAULT_PUE = PUE_AIR

# US enterprise / large-industrial all-in electricity rate. EIA 2026 national
# industrial average is ~$0.085/kWh; major DC markets (NoVA, Phoenix, Dallas)
# are $0.057–$0.068/kWh wholesale; hyperscaler PPAs $0.056–$0.066/kWh.
# $0.10 is a defensible single default for a self-operated enterprise GPU
# cluster (slightly above wholesale to capture transmission + small overhead).
DEFAULT_COST_PER_KWH_USD = 0.10
DEFAULT_HOURS_PER_MONTH = 730  # 8760 / 12
DEFAULT_AMORTIZATION_MONTHS = 36


@dataclass
class CostResult:
    capex_usd: float
    opex_monthly_usd: float
    tco_36m_usd: float
    tokens_per_usd_per_month: float
    power_kw: float


def calc_tco(
    gpu_count: int,
    gpu_price_usd: float | None,
    tdp_watts: int | None,
    tokens_per_sec: float,
    network_switch_cost_usd: float = 0.0,
    storage_cost_usd: float = 0.0,
    pue: float | None = None,
    cost_per_kwh_usd: float = DEFAULT_COST_PER_KWH_USD,
    amortization_months: int = DEFAULT_AMORTIZATION_MONTHS,
    cooling_type: str | None = None,
) -> CostResult:
    """
    Calculate Total Cost of Ownership in USD.

    CapEx = (gpu_price × gpu_count) + network_switch_cost + storage_cost
    OpEx_monthly = (total_tdp_kw × PUE × hours_per_month × cost_per_kwh)
    TCO = CapEx + (OpEx_monthly × amortization_months)

    PUE selection: explicit ``pue`` wins; else derived from ``cooling_type``
    ("liquid" → 1.15, "air" → 1.40); else falls back to DEFAULT_PUE.
    """
    # CapEx
    if gpu_price_usd is None:
        gpu_price_usd = estimate_gpu_price(gpu_count)

    capex_usd = (gpu_price_usd * gpu_count) + network_switch_cost_usd + storage_cost_usd

    # OpEx (power)
    if tdp_watts is None:
        tdp_watts = 1000  # 2026 default — Blackwell-class

    if pue is None:
        if cooling_type == "liquid":
            pue = PUE_LIQUID
        elif cooling_type == "air":
            pue = PUE_AIR
        else:
            pue = DEFAULT_PUE

    total_power_kw = (tdp_watts * gpu_count) / 1000.0
    effective_power_kw = total_power_kw * pue
    opex_monthly = effective_power_kw * DEFAULT_HOURS_PER_MONTH * cost_per_kwh_usd

    # TCO
    tco = capex_usd + (opex_monthly * amortization_months)

    # Tokens per dollar (per month)
    tokens_per_month = tokens_per_sec * 3600 * 24 * 30  # Assume continuous operation
    monthly_cost = tco / amortization_months
    tokens_per_usd = tokens_per_month / monthly_cost if monthly_cost > 0 else 0

    return CostResult(
        capex_usd=capex_usd,
        opex_monthly_usd=opex_monthly,
        tco_36m_usd=tco,
        tokens_per_usd_per_month=tokens_per_usd,
        power_kw=total_power_kw,
    )


def estimate_gpu_price(gpu_count: int) -> float:
    """Fallback price estimate (USD) if MSRP not available.

    Generic blended midpoint: H100 ~$30k, H200 ~$35k, B200 ~$40k as of 2026.
    """
    return 35000.0


def calc_network_cost(nodes: int, switch_type: str = "IB_NDR") -> float:
    """Estimate network fabric cost (USD) per host port (all-in: switch slice + NIC + optics + cabling).

    2026 channel pricing — Quantum-2 NDR chassis is ~$1.5k/port, but a full host
    port includes ConnectX-7 NIC (~$2.5k) + OSFP transceiver pair (~$1.5k), so
    all-in lands around $5k for NDR. Other tiers scaled similarly.
    """
    switch_costs = {
        "IB_NDR": 5000,    # 400G InfiniBand (Quantum-2)
        "IB_XDR": 8000,    # 800G InfiniBand (Quantum-X800)
        "RoCEv2": 3000,    # 400G RoCE
        "Ethernet_400G": 2000,
    }
    cost_per_port = switch_costs.get(switch_type, 5000)
    # Each node needs at least 1 uplink; add spine switches for >4 nodes
    ports_needed = nodes
    if nodes > 4:
        ports_needed = nodes * 2  # Leaf + spine
    return cost_per_port * ports_needed
