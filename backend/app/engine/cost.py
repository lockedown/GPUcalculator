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
# Default amortisation. AWS uses 5yr (60mo), Meta 5.5yr, Google/Oracle 6yr —
# 48mo is the middle ground for an enterprise persona. UI exposes 36/48/60.
DEFAULT_AMORTIZATION_MONTHS = 48

# --- Run-cost defaults (USD) ---
# Colocation / facility rent. CBRE H2 2025 reports ~$195/kW-month for
# 250-500 kW deployments in major US DC markets. Charged on IT-kW reserved;
# *separate* from the metered electricity above (the kWh charge covers actual
# energy drawn including PUE losses, the colo fee covers space/cooling/UPS).
DEFAULT_COLO_USD_PER_KW_PER_MONTH = 200.0

# Hardware support / maintenance contract (Dell ProSupport, NVIDIA Mission
# Control, etc.) — typical 8-15% of CapEx per year for AI hardware. Use 10%.
DEFAULT_HW_SUPPORT_PCT_OF_CAPEX_PER_YEAR = 0.10

# Software licensing — NVIDIA AI Enterprise published list ~$1,000/GPU/yr
# (5-year term included free with H100/H200; charged separately for others).
DEFAULT_SOFTWARE_USD_PER_GPU_PER_YEAR = 1000.0


@dataclass
class CostResult:
    capex_usd: float
    opex_monthly_usd: float
    # Itemised monthly OpEx so the UI can render a transparent breakdown.
    opex_breakdown: dict
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
    colo_usd_per_kw_per_month: float = DEFAULT_COLO_USD_PER_KW_PER_MONTH,
    hw_support_pct_of_capex_per_year: float = DEFAULT_HW_SUPPORT_PCT_OF_CAPEX_PER_YEAR,
    software_usd_per_gpu_per_year: float = DEFAULT_SOFTWARE_USD_PER_GPU_PER_YEAR,
) -> CostResult:
    """Calculate Total Cost of Ownership in USD.

    CapEx = (gpu_price × gpu_count) + network_switch_cost + storage_cost

    OpEx (monthly) = power + colocation + hardware support + software
        power     = total_tdp_kw × PUE × hours_per_month × cost_per_kwh
        colo      = total_tdp_kw × colo_usd_per_kw_per_month   (IT-kW reserved)
        support   = capex × hw_support_pct_of_capex_per_year / 12
        software  = gpu_count × software_usd_per_gpu_per_year / 12

    TCO = CapEx + (OpEx_monthly × amortization_months)

    To zero out any of the four OpEx lines, pass ``0.0`` for the matching
    parameter (e.g. ``colo_usd_per_kw_per_month=0.0`` for self-operated DCs
    where the rent is already capitalised elsewhere).

    PUE selection: explicit ``pue`` wins; else derived from ``cooling_type``
    ("liquid" → 1.15, "air" → 1.40); else falls back to DEFAULT_PUE.
    """
    # CapEx
    if gpu_price_usd is None:
        gpu_price_usd = estimate_gpu_price(gpu_count)

    capex_usd = (gpu_price_usd * gpu_count) + network_switch_cost_usd + storage_cost_usd

    # OpEx — power
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
    power_opex_monthly = effective_power_kw * DEFAULT_HOURS_PER_MONTH * cost_per_kwh_usd

    # OpEx — colocation (charged on IT-kW reserved, *not* PUE-adjusted —
    # the kWh charge above covers the PUE losses; this covers space/UPS/cooling).
    colo_opex_monthly = total_power_kw * colo_usd_per_kw_per_month

    # OpEx — hardware support contract (% of CapEx per year, monthly slice)
    support_opex_monthly = capex_usd * hw_support_pct_of_capex_per_year / 12.0

    # OpEx — software licensing (per GPU per year, monthly slice)
    software_opex_monthly = gpu_count * software_usd_per_gpu_per_year / 12.0

    opex_monthly = (
        power_opex_monthly + colo_opex_monthly + support_opex_monthly + software_opex_monthly
    )

    opex_breakdown = {
        "power_usd": round(power_opex_monthly, 2),
        "colocation_usd": round(colo_opex_monthly, 2),
        "hw_support_usd": round(support_opex_monthly, 2),
        "software_usd": round(software_opex_monthly, 2),
    }

    # TCO
    tco = capex_usd + (opex_monthly * amortization_months)

    # Tokens per dollar (per month). Note: monthly_cost includes the new OpEx
    # lines, so tokens/$ is meaningfully lower than before — that's the point.
    tokens_per_month = tokens_per_sec * 3600 * 24 * 30  # Assume continuous operation
    monthly_cost = tco / amortization_months
    tokens_per_usd = tokens_per_month / monthly_cost if monthly_cost > 0 else 0

    return CostResult(
        capex_usd=capex_usd,
        opex_monthly_usd=opex_monthly,
        opex_breakdown=opex_breakdown,
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
