/**
 * Single source of truth for the dashboard's default workload + constraints.
 *
 * Both ``lib/store.ts`` (zustand state init) and ``lib/url-state.ts``
 * (share-link encode/decode) need these values to agree — keeping them in
 * separate files would silently drift on every new field. Import from here.
 */

import type { ConstraintInput, WorkloadInput } from "@/types";

export const DEFAULT_WORKLOAD: WorkloadInput = {
  model_params_b: 70,
  precision: "FP16",
  context_length: 4096,
  concurrent_users: 1,
  workload_type: "inference",
  batch_size: 1,
  is_moe: false,
  num_experts: 8,
  active_experts: 2,
  finance_benchmark_category: null,
  multi_tenancy_mode: "dedicated",
  mig_profile: null,
  tenants: 1,
  serving_mode: "colocated",
};

export const DEFAULT_CONSTRAINTS: ConstraintInput = {
  max_budget_usd: null,
  max_power_per_rack_kw: null,
  cooling_type: "air",
  max_lead_time_weeks: null,
  amortization_months: 48,
  colo_usd_per_kw_per_month: 200,
  hw_support_pct_of_capex_per_year: 0.10,
  software_usd_per_gpu_per_year: 1000,
  metric_weights: {
    performance: 0.35,
    cost: 0.30,
    complexity: 0.15,
    availability: 0.20,
  },
  target_tpot_ms: null,
};
