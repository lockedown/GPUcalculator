/**
 * Shared enums + their UI option arrays. No dependencies on other type files,
 * so this is the foundation everything else imports from.
 */

// ---- Multi-tenancy / fractional GPU (Sprint 11) ----
export type TenancyMode = "dedicated" | "mig" | "runai_fractional";
export type MigProfile = "1g.10gb" | "2g.20gb" | "3g.40gb" | "4g.40gb" | "7g.full";

export const TENANCY_MODE_OPTIONS: { value: TenancyMode; label: string }[] = [
  { value: "dedicated", label: "Dedicated (one workload owns the GPU)" },
  { value: "mig", label: "MIG (NVIDIA hardware partition — Hopper only)" },
  { value: "runai_fractional", label: "Run:ai fractional (software time-slicing)" },
];

export const MIG_PROFILE_OPTIONS: { value: MigProfile; label: string }[] = [
  { value: "1g.10gb", label: "1g.10gb · 1/7 compute · 1/8 memory · 7/GPU" },
  { value: "2g.20gb", label: "2g.20gb · 2/7 compute · 1/4 memory · 3/GPU" },
  { value: "3g.40gb", label: "3g.40gb · 3/7 compute · 1/2 memory · 2/GPU" },
  { value: "4g.40gb", label: "4g.40gb · 4/7 compute · 1/2 memory · 1/GPU" },
  { value: "7g.full", label: "7g.full · full GPU as one MIG instance" },
];

// ---- Disaggregated prefill/decode (Sprint 10) ----
export type ServingMode = "colocated" | "disaggregated";

export const SERVING_MODE_OPTIONS: { value: ServingMode; label: string }[] = [
  { value: "colocated", label: "Colocated (one pool runs prefill + decode)" },
  { value: "disaggregated", label: "Disaggregated (separate prefill / decode pools — Dynamo)" },
];

// ---- NVLink fabric topology (Sprint 9b) ----
export type NVLinkTopology = "nvswitch" | "nvl_fabric" | "point_to_point" | "none";

// Human-readable labels + tooltips for the hardware page topology stat.
export const NVLINK_TOPOLOGY_LABELS: Record<NVLinkTopology, { label: string; tooltip: string }> = {
  nvswitch: {
    label: "NVSwitch",
    tooltip:
      "Full bisection bandwidth across the 8-GPU baseboard via the NVSwitch ASIC. Standard on HGX and DGX systems — every GPU pair gets full link rate.",
  },
  nvl_fabric: {
    label: "NVL Fabric",
    tooltip:
      "Rack-scale unified NVLink fabric (NVL72). Single-hop bandwidth across all 72 GPUs in the rack, treated as one effective node.",
  },
  point_to_point: {
    label: "Point-to-point",
    tooltip:
      "Direct NVLink / Infinity Fabric mesh (no switch). Adjacent peers get full link rate; non-adjacent traffic takes 2 hops, costing ~15% on TP > 4 (matches NCCL/RCCL all-reduce benchmarks).",
  },
  none: {
    label: "PCIe only",
    tooltip:
      "No multi-GPU NVLink fabric — each card is an island on PCIe. Tensor parallelism is not available; multi-GPU scales DP-only.",
  },
};

// ---- Workload categories ----
export const WORKLOAD_CATEGORIES = [
  { value: "inference", label: "LLM Inference" },
  { value: "training", label: "Training" },
  { value: "quant", label: "Quantitative Finance" },
  { value: "risk", label: "Risk & Compliance" },
  { value: "hpc", label: "HPC / Scientific" },
  { value: "trading", label: "Trading Systems" },
] as const;

export const BENCHMARK_CATEGORIES = [
  { value: "quant", label: "Quantitative" },
  { value: "risk", label: "Risk & Compliance" },
  { value: "inference", label: "AI / Inference" },
  { value: "hpc", label: "HPC" },
  { value: "trading", label: "Trading" },
  { value: "tokenization", label: "Tokenization" },
] as const;

export const PRECISION_OPTIONS = ["FP4", "FP8", "FP16", "BF16", "FP32"] as const;

// ---- Regional pricing + grid intensity (Sprint v2.2) ----
// The frontend region picker is a UI affordance over the existing constraint
// fields — selecting a region just sets ``colo_usd_per_kw_per_month`` and
// ``grid_carbon_intensity_g_kwh`` to the regional preset values. The backend
// stays region-agnostic; it only sees the resulting numbers.
//
// Colocation rates from CBRE H2 2025 / 2026 outlook for major DC markets.
// Grid intensity from EPA eGRID 2024 (US sub-regions) and IEA 2024 (EU/APAC
// production-mix averages). APAC is coal-heavy; EU is the cleanest of the
// large markets after the post-2022 renewables build-out.
export type Region = "US-East" | "US-West" | "EU" | "APAC";

export interface RegionPreset {
  label: string;
  colo_usd_per_kw_per_month: number;
  grid_carbon_intensity_g_kwh: number;
  blurb: string;
}

export const REGION_PRESETS: Record<Region, RegionPreset> = {
  "US-East": {
    label: "US East (NoVA / PJM)",
    colo_usd_per_kw_per_month: 195,
    grid_carbon_intensity_g_kwh: 380,
    blurb: "PJM grid; CBRE NoVA $195/kW-mo. The default — most US enterprise hyperscaler footprints.",
  },
  "US-West": {
    label: "US West (PNW / Cascade)",
    colo_usd_per_kw_per_month: 210,
    grid_carbon_intensity_g_kwh: 250,
    blurb: "Pacific NW hydro-heavy grid (cleaner). Power costs slightly higher than US-East.",
  },
  "EU": {
    label: "EU (FR / NL / IE blend)",
    colo_usd_per_kw_per_month: 230,
    grid_carbon_intensity_g_kwh: 270,
    blurb: "FRA / AMS / DUB blend. Higher rents but cleaner grid; energy costs above US.",
  },
  "APAC": {
    label: "APAC (SG / TYO / SYD blend)",
    colo_usd_per_kw_per_month: 180,
    grid_carbon_intensity_g_kwh: 550,
    blurb: "SIN / TYO / SYD blend. Cheapest rents but coal-heavy grid pushes carbon up sharply.",
  },
};

export const REGION_OPTIONS: { value: Region; label: string }[] = (
  Object.entries(REGION_PRESETS) as [Region, RegionPreset][]
).map(([value, p]) => ({ value, label: p.label }));

// ---- Per-GPU brand colours used by charts + cards ----
export const GPU_COLORS: Record<string, string> = {
  "H200 SXM5": "#1d6ed8",
  "B200 SXM": "#b45309",
  "B300 SXM": "#c2410c",
  "GB200 NVL72": "#6d28d9",
  "GB300 NVL72": "#0077cc",
  "MI300X": "#b91c1c",
  "MI350X": "#be185d",
  "MI355X": "#c2192e",
};
