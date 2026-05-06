/**
 * Sizing-engine output shapes: per-GPU evaluation result + topology / rack
 * sub-results, plus the wrapper returned by ``/api/compare``.
 */

import type { ServingMode, TenancyMode } from "./enums";
import type { ConstraintInput, WorkloadInput } from "./workload";

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
  // Disaggregated prefill/decode view. Mirrors gpu_count in colocated mode.
  serving_mode: ServingMode;
  prefill_gpu_count: number | null;
  decode_gpu_count: number | null;
  prefill_role_strategy: string | null;
  decode_role_strategy: string | null;
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
  // Annual operating-emissions estimate (kg CO2-equivalent per year) at the
  // configured grid intensity. PUE-adjusted so cooling overhead is included.
  carbon_kg_per_year: number | null;
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

export interface ComparisonResponse {
  workload: WorkloadInput;
  constraints: ConstraintInput;
  results: GPUResult[];
  sweet_spot_gpu: string | null;
  // Up to 3 short reasons explaining why ``sweet_spot_gpu`` was chosen.
  // Empty when no GPUs were evaluated.
  sweet_spot_reasons: string[];
}
