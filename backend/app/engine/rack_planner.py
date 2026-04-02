"""Power-aware rack planning engine.

Computes rack density, cooling capacity, PDU constraints, and physical
layout for a GPU deployment topology.

Industry standard rack specs:
  - Standard 42U rack
  - Typical PDU: 2× 60A/208V three-phase = ~25kW per PDU, 50kW total
  - High-density liquid-cooled racks: up to 100-120kW per rack
  - Air-cooled racks: typically capped at 20-30kW
"""

from dataclasses import dataclass
import math


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

# PDU tiers
PDU_TIERS: dict[str, dict] = {
    "standard_air": {
        "label": "Standard Air-Cooled",
        "max_kw": 25.0,
        "pdu_count": 2,
        "voltage": 208,
        "amps_per_pdu": 60,
    },
    "high_density_air": {
        "label": "High-Density Air-Cooled",
        "max_kw": 40.0,
        "pdu_count": 2,
        "voltage": 415,
        "amps_per_pdu": 60,
    },
    "liquid_cooled": {
        "label": "Liquid-Cooled",
        "max_kw": 100.0,
        "pdu_count": 2,
        "voltage": 415,
        "amps_per_pdu": 150,
    },
    "ultra_liquid": {
        "label": "Ultra-Dense Liquid",
        "max_kw": 120.0,
        "pdu_count": 4,
        "voltage": 415,
        "amps_per_pdu": 150,
    },
}

# Cooling capacity by type (kW removable per rack)
COOLING_CAPACITY: dict[str, float] = {
    "air": 30.0,       # Best-case with hot/cold aisle containment
    "liquid": 120.0,    # Direct-to-chip liquid cooling
}

# Overhead: networking, management, UPS per rack
OVERHEAD_KW_PER_RACK = 1.5     # TOR switch + BMC + misc
OVERHEAD_U_PER_RACK = 4        # TOR switches, cable management, PDU space


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


def plan_rack_layout(
    gpu_name: str,
    gpu_count: int,
    tdp_watts: int,
    form_factor: str,
    cooling_type: str = "air",
    max_power_per_rack_kw: float | None = None,
    is_rack_scale: bool = False,
    rack_gpu_count: int | None = None,
    pue: float = 1.3,
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
        pue: Power Usage Effectiveness multiplier
    """
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
    # Server overhead: ~10% for CPU, NIC, fans, PSU inefficiency
    power_per_gpu_kw = tdp_watts / 1000.0
    server_overhead_kw = gpus_per_server * power_per_gpu_kw * 0.10
    power_per_server_kw = (gpus_per_server * power_per_gpu_kw) + server_overhead_kw

    # --- Servers needed ---
    total_servers = math.ceil(gpu_count / gpus_per_server)

    # --- How many servers fit per rack (U-space limited) ---
    usable_u = RACK_HEIGHT_U - OVERHEAD_U_PER_RACK
    max_servers_by_u = max(1, usable_u // u_per_server)

    # --- How many servers fit per rack (power limited) ---
    # Select PDU tier based on cooling type
    if cooling_type == "liquid":
        pdu_tier_key = "liquid_cooled"
    else:
        pdu_tier_key = "high_density_air" if power_per_server_kw > 5.0 else "standard_air"

    pdu = PDU_TIERS[pdu_tier_key]
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

    # --- Cooling ---
    cooling_cap = COOLING_CAPACITY.get(cooling_type, 30.0)
    cooling_headroom_pct = max(0.0, ((cooling_cap - power_per_rack_kw) / cooling_cap) * 100)
    fits_cooling = power_per_rack_kw <= cooling_cap

    # --- Constraint check ---
    fits_power = True
    if max_power_per_rack_kw:
        fits_power = power_per_rack_kw <= max_power_per_rack_kw

    # --- Density warning ---
    density_warning = None
    if not fits_cooling:
        density_warning = f"Rack power {power_per_rack_kw:.1f}kW exceeds {cooling_type} cooling capacity ({cooling_cap:.0f}kW)"
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
