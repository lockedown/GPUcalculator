"""Multi-tenancy / fractional GPU sizing.

Three modes are supported:

* ``dedicated`` — default; one workload owns the GPU. No spec adjustments.
* ``mig`` — NVIDIA MIG hardware partitioning. Hopper-class only (H100/H200).
  A MIG instance gets a fixed slice of compute (in 1/7 GPC units) and memory
  (in 1/8 HBM-stack units).  NVLink between MIG instances is **disabled** by
  hardware, so tensor-parallelism across instances is impossible — each tenant
  is effectively running on a "PCIe-class" islet.  We surface this with the
  ``MIG_NVLINK_DISABLED`` advisory.
* ``runai_fractional`` — software time-slicing (Run:ai, NVIDIA vGPU
  time-slicing). Each tenant sees the *full* GPU resources but throughput is
  divided across N tenants. Add a small KV-cache fragmentation penalty (5%) to
  reflect cache-eviction churn under co-tenancy.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# MIG profile catalogue
# ---------------------------------------------------------------------------
# compute_fraction is in units of 1/7 (GPC count); memory_fraction is in units
# of 1/8 (HBM-stack slices). instances_per_gpu is the max number of independent
# tenants of this profile that can be configured on a single GPU.
MIG_PROFILES: dict[str, dict] = {
    "1g.10gb": {"compute_fraction": 1 / 7, "memory_fraction": 1 / 8, "instances_per_gpu": 7},
    "2g.20gb": {"compute_fraction": 2 / 7, "memory_fraction": 2 / 8, "instances_per_gpu": 3},
    "3g.40gb": {"compute_fraction": 3 / 7, "memory_fraction": 4 / 8, "instances_per_gpu": 2},
    "4g.40gb": {"compute_fraction": 4 / 7, "memory_fraction": 4 / 8, "instances_per_gpu": 1},
    "7g.full": {"compute_fraction": 1.0,    "memory_fraction": 1.0,    "instances_per_gpu": 1},
}

# Generations that ship hardware MIG support.  Blackwell adds finer-grained
# partitioning but the public schema isn't finalised yet — keep restrictive.
MIG_SUPPORTED_GENERATIONS: set[str] = {"Hopper"}

# Run:ai / vGPU time-slicing pays a small effective-bandwidth penalty due to
# KV-cache eviction churn between tenant context swaps.  5% reflects the
# observed steady-state overhead in Run:ai's published benchmarks.
RUNAI_KV_FRAGMENTATION_PENALTY = 0.05


@dataclass
class EffectiveSpecs:
    """Per-tenant view of a GPU after tenancy is applied."""
    memory_gb: float
    mem_bandwidth_tb_s: float
    bf16_tflops: float
    fp8_tflops: float | None
    fp4_tflops: float | None
    # max_tp = 1 for MIG (NVLink disabled across instances).  For dedicated
    # and runai_fractional, it stays the GPU's max_gpus_per_node.
    max_tp: int
    # interconnect_type drives the topology routing.  MIG is forced to "PCIe"
    # so calc_topology takes the no-tensor-parallelism branch.
    interconnect_type: str
    # Per-tenant aggregate throughput divisor.  Run:ai time-slicing → tenants;
    # MIG and dedicated → 1.0.
    throughput_divisor: float
    # Number of tenants that fit on one physical GPU (MIG: profile-defined;
    # runai_fractional: requested tenants count; dedicated: 1).
    instances_per_gpu: int
    tenancy_mode_applied: str
    # Stable codes — soft (advisory, kept on result) and hard (terminate
    # evaluate_gpu before performance calc).
    advisory_codes: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)


def apply_tenancy(
    gpu,
    mode: str,
    mig_profile: str | None,
    tenants: int,
) -> EffectiveSpecs:
    """Return the per-tenant effective specs for ``gpu`` under ``mode``.

    Hard-fail conditions populate ``error_codes`` and return early without
    further spec adjustment — callers should short-circuit and surface those
    violations.  Soft-fail conditions accumulate in ``advisory_codes`` and
    spec adjustments still apply.
    """
    base_memory = gpu.memory_gb if getattr(gpu, "memory_gb", None) is not None else gpu.hbm_capacity_gb
    base_interconnect = (
        getattr(gpu, "interconnect_type", None)
        or getattr(gpu, "intra_node_interconnect", None)
        or "Unknown"
    )
    specs = EffectiveSpecs(
        memory_gb=base_memory,
        mem_bandwidth_tb_s=gpu.mem_bandwidth_tb_s,
        bf16_tflops=gpu.bf16_tflops or 0.0,
        fp8_tflops=getattr(gpu, "fp8_tflops", None),
        fp4_tflops=getattr(gpu, "fp4_tflops", None),
        max_tp=getattr(gpu, "max_gpus_per_node", None) or 8,
        interconnect_type=base_interconnect,
        throughput_divisor=1.0,
        instances_per_gpu=1,
        tenancy_mode_applied=mode,
    )

    if mode == "dedicated" or mode is None:
        return specs

    if mode == "mig":
        if gpu.generation not in MIG_SUPPORTED_GENERATIONS:
            specs.error_codes.append("MIG_NOT_SUPPORTED")
            return specs
        if getattr(gpu, "is_rack_scale", False):
            # NVL72 cannot expose MIG instances via the rack fabric.
            specs.error_codes.append("MIG_NOT_SUPPORTED")
            return specs
        if not mig_profile or mig_profile not in MIG_PROFILES:
            specs.error_codes.append("MIG_PROFILE_REQUIRED")
            return specs

        profile = MIG_PROFILES[mig_profile]
        cf = profile["compute_fraction"]
        mf = profile["memory_fraction"]

        specs.memory_gb = base_memory * mf
        specs.mem_bandwidth_tb_s = gpu.mem_bandwidth_tb_s * mf
        specs.bf16_tflops = (gpu.bf16_tflops or 0.0) * cf
        if specs.fp8_tflops is not None:
            specs.fp8_tflops *= cf
        if specs.fp4_tflops is not None:
            specs.fp4_tflops *= cf
        # MIG instances cannot share NVLink — force PCIe-class topology.
        specs.max_tp = 1
        specs.interconnect_type = "PCIe"
        specs.instances_per_gpu = profile["instances_per_gpu"]
        specs.advisory_codes.append("MIG_NVLINK_DISABLED")
        return specs

    if mode == "runai_fractional":
        if tenants <= 1:
            # Time-slicing with one tenant is a no-op; treat as dedicated.
            specs.tenancy_mode_applied = "dedicated"
            return specs
        # Full memory + compute; throughput divided across tenants; small KV
        # fragmentation penalty on memory bandwidth.
        specs.mem_bandwidth_tb_s *= 1.0 - RUNAI_KV_FRAGMENTATION_PENALTY
        specs.throughput_divisor = float(tenants)
        specs.instances_per_gpu = tenants
        specs.advisory_codes.append("RUNAI_TIME_SLICED")
        return specs

    # Unknown mode — treat as dedicated, no advisory.
    specs.tenancy_mode_applied = "dedicated"
    return specs


class TenancyGPUShim:
    """GPU-like wrapper that surfaces per-tenant effective specs to callers
    that read ``gpu.<attr>`` directly (e.g. ``calc_topology``).

    Unspecified attributes pass through to the underlying GPU.  The shim is
    transient — used only for one ``evaluate_gpu`` call — so we don't cache.
    """

    def __init__(self, gpu, specs: EffectiveSpecs):
        # Bypass our __getattr__ for these two slots.
        object.__setattr__(self, "_gpu", gpu)
        object.__setattr__(
            self,
            "_overrides",
            {
                "memory_gb": specs.memory_gb,
                "hbm_capacity_gb": specs.memory_gb,
                "mem_bandwidth_tb_s": specs.mem_bandwidth_tb_s,
                "bf16_tflops": specs.bf16_tflops,
                "fp8_tflops": specs.fp8_tflops,
                "fp4_tflops": specs.fp4_tflops,
                "interconnect_type": specs.interconnect_type,
                "max_gpus_per_node": specs.max_tp,
            },
        )

    def __getattr__(self, name):
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_gpu"), name)

