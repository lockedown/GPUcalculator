export interface GPU {
  id: number;
  name: string;
  vendor: string;
  generation: string;
  form_factor: string;
  hbm_capacity_gb: number;
  hbm_type: string | null;
  mem_bandwidth_tb_s: number;
  bf16_tflops: number | null;
  fp64_tflops: number | null;
  fp8_tflops: number | null;
  fp4_tflops: number | null;
  tdp_watts: number | null;
  cooling_type: string;
  intra_node_interconnect: string | null;
  interconnect_bw_gb_s: number | null;
  // Intra-node fabric topology — drives bandwidth-derate decisions.
  // Values: 'nvswitch' | 'nvl_fabric' | 'point_to_point' | 'none' | null.
  nvlink_topology: NVLinkTopology | null;
  max_gpus_per_node: number;
  is_rack_scale: boolean;
  rack_gpu_count: number | null;
  rack_fabric_bw_tb_s: number | null;
  msrp_usd: number | null;
  is_estimated: boolean;
  release_date: string | null;
  verdict: string | null;
}

export interface GPUDetail extends GPU {
  benchmarks: BenchmarkScore[];
  availability: AvailabilityInfo | null;
}

export interface BenchmarkScore {
  id: number;
  gpu_id: number;
  benchmark_name: string;
  workload_category: string;
  workload_description: string | null;
  rating: string | null;
  bar_pct: number | null;
  metric_value: string | null;
  metric_numeric: number | null;
  metric_unit: string | null;
}

export interface BenchmarkWithGPU extends BenchmarkScore {
  gpu_name: string | null;
  gpu_vendor: string | null;
}

export interface AvailabilityInfo {
  id: number;
  gpu_id: number;
  lead_time_weeks: number;
  supply_status: string;
}

export interface NetworkingOption {
  id: number;
  name: string;
  type: string;
  vendor: string;
  generation: string | null;
  bandwidth_gb_s: number;
  latency_us: number | null;
  is_inter_node: number;
  notes: string | null;
}

export interface WorkloadInput {
  model_params_b: number;
  precision: string;
  context_length: number;
  concurrent_users: number;
  workload_type: string;
  batch_size: number;
  is_moe: boolean;
  num_experts: number;
  active_experts: number;
  finance_benchmark_category: string | null;
  // Multi-tenancy / fractional GPU.  See backend tenancy.py.
  multi_tenancy_mode: TenancyMode;
  mig_profile: MigProfile | null;
  tenants: number;
}

export type TenancyMode = "dedicated" | "mig" | "runai_fractional";
export type MigProfile = "1g.10gb" | "2g.20gb" | "3g.40gb" | "4g.40gb" | "7g.full";
export type NVLinkTopology = "nvswitch" | "nvl_fabric" | "point_to_point" | "none";

// Human-readable labels for nvlink_topology, used by the hardware page.
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

export const MIG_PROFILE_OPTIONS: { value: MigProfile; label: string }[] = [
  { value: "1g.10gb", label: "1g.10gb · 1/7 compute · 1/8 memory · 7/GPU" },
  { value: "2g.20gb", label: "2g.20gb · 2/7 compute · 1/4 memory · 3/GPU" },
  { value: "3g.40gb", label: "3g.40gb · 3/7 compute · 1/2 memory · 2/GPU" },
  { value: "4g.40gb", label: "4g.40gb · 4/7 compute · 1/2 memory · 1/GPU" },
  { value: "7g.full", label: "7g.full · full GPU as one MIG instance" },
];

export const TENANCY_MODE_OPTIONS: { value: TenancyMode; label: string }[] = [
  { value: "dedicated", label: "Dedicated (one workload owns the GPU)" },
  { value: "mig", label: "MIG (NVIDIA hardware partition — Hopper only)" },
  { value: "runai_fractional", label: "Run:ai fractional (software time-slicing)" },
];

export interface ConstraintInput {
  max_budget_usd: number | null;
  max_power_per_rack_kw: number | null;
  cooling_type: string;
  max_lead_time_weeks: number | null;
  amortization_months: number;  // 36 | 48 | 60
  // Run-cost OpEx components — set any to 0 to opt out of that line.
  colo_usd_per_kw_per_month: number;
  hw_support_pct_of_capex_per_year: number;
  software_usd_per_gpu_per_year: number;
  metric_weights: {
    performance: number;
    cost: number;
    complexity: number;
    availability: number;
  };
  // Optional per-user latency target (ms). Candidates whose TPOT exceeds it
  // get the TPOT_MISSED advisory; ranking is unaffected.
  target_tpot_ms: number | null;
}

export interface TopologyResult {
  gpu_count: number;
  nodes: number;
  gpus_per_node: number;
  parallelism_strategy: string;
  tp_degree: number;
  pp_degree: number;
  dp_degree: number;
  effective_bandwidth_gb_s: number | null;
  cross_node_latency_penalty: number;
}

export interface RackPlanResult {
  total_racks: number;
  servers_per_rack: number;
  gpus_per_rack: number;
  u_per_server: number;
  u_utilization_pct: number;
  power_per_gpu_kw: number;
  power_per_server_kw: number;
  power_per_rack_kw: number;
  total_power_kw: number;
  pue_adjusted_power_kw: number;
  pdu_tier: string;
  pdu_tier_label: string;
  pdu_headroom_pct: number;
  cooling_type: string;
  cooling_capacity_kw: number;
  cooling_headroom_pct: number;
  fits_power_constraint: boolean;
  fits_cooling: boolean;
  density_warning: string | null;
}

export interface GPUResult {
  gpu_id: number;
  gpu_name: string;
  gpu_vendor: string;
  tokens_per_sec: number | null;
  prefill_tokens_per_sec: number | null;
  decode_tokens_per_sec: number | null;
  // Per-user latency view at the configured concurrency.
  ttft_ms: number | null;
  tpot_ms: number | null;
  per_user_decode_tps: number | null;
  // Multi-tenancy view — populated only when multi_tenancy_mode != "dedicated".
  tenancy_mode_applied: TenancyMode | null;
  tenants_per_gpu: number | null;
  per_tenant_decode_tps: number | null;
  per_tenant_kv_cache_gb: number | null;
  // MoE-specific surfacing — populated only when workload.is_moe.
  moe_active_param_fraction: number | null;
  moe_effective_bw_per_token_gb: number | null;
  moe_routing_overhead_pct: number | null;
  kv_cache_gb: number | null;
  max_context_length: number | null;
  tco_usd: number | null;
  capex_usd: number | null;
  opex_monthly_usd: number | null;
  // Itemised monthly OpEx components in USD.
  opex_breakdown: {
    power_usd: number;
    colocation_usd: number;
    hw_support_usd: number;
    software_usd: number;
  } | null;
  tokens_per_usd: number | null;
  complexity_score: number | null;
  availability_score: number | null;
  composite_score: number | null;
  topology: TopologyResult | null;
  rack_plan: RackPlanResult | null;
  benchmark_scores: Record<string, number> | null;
  is_estimated: boolean;
  warnings: string[];
  // Stable codes for constraint violations / advisories. See backend
  // `app.engine.optimizer.Violation` for the full list.
  violation_codes: string[];
}

export interface PriceHistoryEntry {
  id: number;
  gpu_id: number;
  date: string;
  price_usd: number;
  source: string;
}

export interface PriceHistoryByGPU {
  gpu_id: number;
  gpu_name: string;
  prices: PriceHistoryEntry[];
}

export interface ComparisonResponse {
  workload: WorkloadInput;
  constraints: ConstraintInput;
  results: GPUResult[];
  sweet_spot_gpu: string | null;
}

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
