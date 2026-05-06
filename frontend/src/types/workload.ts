/**
 * Workload + constraint inputs to the sizing engine. Mirrors the Pydantic
 * schemas in ``backend/app/schemas/workload.py``.
 */

import type { MigProfile, ServingMode, TenancyMode } from "./enums";

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
  // Disaggregated prefill/decode (Sprint 10 — observability v1).
  serving_mode: ServingMode;
}

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
