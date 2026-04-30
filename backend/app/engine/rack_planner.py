"""Power-aware rack planning engine.

Computes rack density, cooling capacity, PDU constraints, and physical
layout for a GPU deployment topology.

Industry standard rack specs (2026):
  - Standard 42U rack
  - Standard air-cooled: ~25 kW per rack PDU (2× 60A/208V 3-phase)
  - High-density air (rear-door heat exchanger): ~40 kW per rack
  - Liquid-cooled (DLC): 100-120 kW (B200/GB200 NVL72 class)
  - Ultra-dense liquid (B300/GB300+, custom CDUs): 120-132 kW
"""

from dataclasses import dataclass
import math

from app.engine.cost import PUE_LIQUID, PUE_AIR


# --- Rack hardware constants ---
RACK_HEIGHT_U = 42

# GPU server form factors (U height and max GPUs per server)
SERVER_FORM_FACTORS: dict[str, dict] = {
    "SXM": {"u_height": 8, "max_gpus": 8, "label": "8-GPU SXM Node"},
    "OAM": {"u_height": 8, "max_gpus": 8, "label": "8-GPU OAM Node"},
    "PCIe": {"u_height": 4, "max_gpus": 4, "label": "4-GPU PCIe Node"},
    "NVL72": {"u_height": 42, "max_gpus": 72, "label": "Full-rack NVL72"},
    "NVL36": {"u_height": 21, "max_gpus": 36, "label": "Half-rack NVL36"},
}

# PDU tiers — max_kw is the rack-power envelope per tier.
# cooling_kw is the matched per-rack heat-removal capacity for that tier:
#   - standard_air: hot/cold aisle containment only
#   - high_density_air: rear-door heat exchanger or in-row cooling
#   - liquid_cooled: direct-to-chip (B200 / GB200 NVL72 class)
#   - ultra_liquid: high-flow CDUs for B300 / GB300 / Vera Rubin class
PDU_TIERS: dict[str, dict] = {
    "standard_air": {
        "label": "Standard Air-Cooled",
        "max_kw": 25.0,
        "cooling_kw": 25.0,
        "pdu_count": 2,
        "voltage": 208,
        "amps_per_pdu": 60,
    },
    "high_density_air": {
        "label": "High-Density Air-Cooled",
        "max_kw": 40.0,
        "cooling_kw": 40.0,
        "pdu_count": 2,
        "voltage": 415,
        "amps_per_pdu": 60,
    },
    "liquid_cooled": {
        "label": "Liquid-Cooled",
        "max_kw": 100.0,
        "cooling_kw": 120.0,
        "pdu_count": 2,
        "voltage": 415,
        "amps_per_pdu": 150,
    },
    "ultra_liquid": {
        "label": "Ultra-Dense Liquid",
        "max_kw": 120.0,
        "cooling_kw": 132.0,
        "pdu_count": 4,
        "voltage": 415,
        "amps_per_pdu": 150,
    },
}

# Per-rack overhead — TOR switch + BMC + UPS + misc.
# 3 kW reflects modern Spectrum-X / Quantum-2 TORs (~2.5 kW) + management (~0.5 kW).
OVERHEAD_KW_PER_RACK = 3.0
OVERHEAD_U_PER_RACK = 4        # TOR switches, cable management, PDU space

# Server-level overhead beyond the GPUs themselves: dual-CPU, NIC, fans, PSU
# inefficiency. 12% is a reasonable midpoint for modern Blackwell-class HGX
# servers (the host platform is genuinely heavy on a B200/B300 baseboard).
SERVER_OVERHEAD_FRACTION = 0.12


@dataclass
class RackPlan:
    """Physical rack deployment plan."""
    # Rack layout
    total_racks: int
    servers_per_rack: int
    gpus_per_rack: int
    u_per_server: int
    u_utilization_pct: float      # % of 42U used

    # Power
    power_per_gpu_kw: float
    power_per_server_kw: float
    power_per_rack_kw: float      # GPU + overhead
    total_power_kw: float
    pue_adjusted_power_kw: float  # After PUE multiplier

    # PDU
    pdu_tier: str
    pdu_tier_label: str
    pdu_headroom_pct: float       # How much PDU capacity remains

    # Cooling
    cooling_type: str
    cooling_capacity_kw: float
    cooling_headroom_pct: float   # How much cooling capacity remains

    # Constraints
    fits_power_constraint: bool
    fits_cooling: bool
    density_warning: str | None = None


def _select_pdu_tier(cooling_type: str, tdp_watts: int, power_per_server_kw: float) -> str:
    """Pick the PDU tier that matches the cooling envelope and density.

    Liquid-cooled: ultra-dense CDU is needed for ≥1200 W per-GPU SKUs
    (B300, GB300, Vera Rubin); standard direct-to-chip handles B200 / GB200
    (≤1000 W) comfortably.
    Air-cooled: high-density (rear-door heat exchanger) when per-server
    power exceeds ~5 kW; otherwise standard CRAC.
    """
    if cooling_type == "liquid":
        return "ultra_liquid" if tdp_watts >= 1200 else "liquid_cooled"
    return "high_density_air" if power_per_server_kw > 5.0 else "standard_air"


def plan_rack_layout(
    gpu_name: str,
    gpu_count: int,
    tdp_watts: int,
    form_factor: str,
    cooling_type: str = "air",
    max_power_per_rack_kw: float | None = None,
    is_rack_scale: bool = False,
    rack_gpu_count: int | None = None,
    pue: float | None = None,
) -> RackPlan:
    """Plan the physical rack layout for a GPU deployment.

    Args:
        gpu_name: GPU model name
        gpu_count: Total GPUs needed
        tdp_watts: Per-GPU TDP in watts
        form_factor: GPU form factor (SXM, OAM, PCIe, NVL72)
        cooling_type: "air" or "liquid"
        max_power_per_rack_kw: User constraint on rack power
        is_rack_scale: Whether this is a rack-scale system (NVL72)
        rack_gpu_count: GPUs per rack for rack-scale systems
        pue: Optional explicit PUE override. If None, derived from
             cooling_type (PUE_LIQUID for liquid, PUE_AIR otherwise) so the
             default matches the cost-engine convention.
    """
    if pue is None:
        pue = PUE_LIQUID if cooling_type == "liquid" else PUE_AIR

    # --- Determine server specs ---
    ff_key = form_factor if form_factor in SERVER_FORM_FACTORS else "SXM"
    if is_rack_scale and rack_gpu_count and rack_gpu_count >= 72:
        ff_key = "NVL72"
    elif is_rack_scale and rack_gpu_count and rack_gpu_count >= 36:
        ff_key = "NVL36"

    ff = SERVER_FORM_FACTORS[ff_key]
    u_per_server = ff["u_height"]
    gpus_per_server = ff["max_gpus"]

    # --- Power per server ---
    power_per_gpu_kw = tdp_watts / 1000.0
    server_overhead_kw = gpus_per_server * power_per_gpu_kw * SERVER_OVERHEAD_FRACTION
    power_per_server_kw = (gpus_per_server * power_per_gpu_kw) + server_overhead_kw

    # --- Servers needed ---
    total_servers = math.ceil(gpu_count / gpus_per_server)

    # --- How many servers fit per rack (U-space limited) ---
    usable_u = RACK_HEIGHT_U - OVERHEAD_U_PER_RACK
    max_servers_by_u = max(1, usable_u // u_per_server)

    # --- PDU tier selection (cooling-aware, density-aware) ---
    pdu_tier_key = _select_pdu_tier(cooling_type, tdp_watts, power_per_server_kw)
    pdu = PDU_TIERS[pdu_tier_key]

    # --- How many servers fit per rack (power limited) ---
    pdu_available_kw = pdu["max_kw"] - OVERHEAD_KW_PER_RACK
    max_servers_by_power = max(1, int(pdu_available_kw / power_per_server_kw))

    # --- User power constraint ---
    if max_power_per_rack_kw:
        user_available_kw = max_power_per_rack_kw - OVERHEAD_KW_PER_RACK
        max_servers_by_user_power = max(1, int(user_available_kw / power_per_server_kw))
    else:
        max_servers_by_user_power = max_servers_by_power

    # Final servers per rack = min of all limits
    servers_per_rack = min(max_servers_by_u, max_servers_by_power, max_servers_by_user_power)

    # Rack-scale overrides
    if ff_key in ("NVL72", "NVL36"):
        servers_per_rack = 1
        total_servers = math.ceil(gpu_count / gpus_per_server)

    gpus_per_rack = servers_per_rack * gpus_per_server
    total_racks = max(1, math.ceil(total_servers / servers_per_rack))

    # --- Power calculations ---
    rack_gpu_power_kw = servers_per_rack * power_per_server_kw
    power_per_rack_kw = rack_gpu_power_kw + OVERHEAD_KW_PER_RACK
    total_power_kw = total_racks * power_per_rack_kw
    pue_adjusted_power_kw = total_power_kw * pue

    # --- U utilization ---
    u_used = (servers_per_rack * u_per_server) + OVERHEAD_U_PER_RACK
    u_utilization_pct = min(100.0, (u_used / RACK_HEIGHT_U) * 100)

    # --- PDU headroom ---
    pdu_headroom_pct = max(0.0, ((pdu["max_kw"] - power_per_rack_kw) / pdu["max_kw"]) * 100)

    # --- Cooling capacity is now tier-matched (RDHX for high-density air,
    # high-flow CDUs for ultra-liquid) rather than a single per-cooling-type number.
    cooling_cap = pdu["cooling_kw"]
    cooling_headroom_pct = max(0.0, ((cooling_cap - power_per_rack_kw) / cooling_cap) * 100)
    fits_cooling = power_per_rack_kw <= cooling_cap

    # --- Constraint check ---
    fits_power = True
    if max_power_per_rack_kw:
        fits_power = power_per_rack_kw <= max_power_per_rack_kw

    # --- Density warning ---
    density_warning = None
    if not fits_cooling:
        density_warning = f"Rack power {power_per_rack_kw:.1f}kW exceeds {pdu['label'].lower()} cooling capacity ({cooling_cap:.0f}kW)"
    elif not fits_power:
        density_warning = f"Rack power {power_per_rack_kw:.1f}kW exceeds user limit ({max_power_per_rack_kw:.0f}kW)"
    elif pdu_headroom_pct < 10:
        density_warning = f"PDU headroom critically low ({pdu_headroom_pct:.0f}%)"

    return RackPlan(
        total_racks=total_racks,
        servers_per_rack=servers_per_rack,
        gpus_per_rack=gpus_per_rack,
        u_per_server=u_per_server,
        u_utilization_pct=round(u_utilization_pct, 1),
        power_per_gpu_kw=round(power_per_gpu_kw, 3),
        power_per_server_kw=round(power_per_server_kw, 2),
        power_per_rack_kw=round(power_per_rack_kw, 2),
        total_power_kw=round(total_power_kw, 2),
        pue_adjusted_power_kw=round(pue_adjusted_power_kw, 2),
        pdu_tier=pdu_tier_key,
        pdu_tier_label=pdu["label"],
        pdu_headroom_pct=round(pdu_headroom_pct, 1),
        cooling_type=cooling_type,
        cooling_capacity_kw=cooling_cap,
        cooling_headroom_pct=round(cooling_headroom_pct, 1),
        fits_power_constraint=fits_power,
        fits_cooling=fits_cooling,
        density_warning=density_warning,
    )
