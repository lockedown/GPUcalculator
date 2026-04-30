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
}

export interface ConstraintInput {
  max_budget_usd: number | null;
  max_power_per_rack_kw: number | null;
  cooling_type: string;
  max_lead_time_weeks: number | null;
  metric_weights: {
    performance: number;
    cost: number;
    complexity: number;
    availability: number;
  };
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
  kv_cache_gb: number | null;
  max_context_length: number | null;
  tco_usd: number | null;
  capex_usd: number | null;
  opex_monthly_usd: number | null;
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
