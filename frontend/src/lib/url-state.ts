/**
 * URL state encoding for shareable scenarios.
 *
 * Encodes the workload + constraints into a query string. To keep links short,
 * only values that differ from the application defaults are emitted; an
 * untouched dashboard produces an empty query string.
 *
 * Field-name keys mirror the API field names so the URL is self-documenting:
 *   /?model_params_b=405&precision=FP8&context_length=131072&cooling_type=liquid
 */

import type { WorkloadInput, ConstraintInput } from "@/types";

// Defaults must match `lib/store.ts` — we omit values matching these from the URL.
const DEFAULT_WORKLOAD: WorkloadInput = {
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
};

const DEFAULT_CONSTRAINTS: ConstraintInput = {
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
};

const WEIGHT_KEYS = ["performance", "cost", "complexity", "availability"] as const;

function isDefault<T>(value: T, defaultValue: T): boolean {
  return value === defaultValue;
}

/**
 * Encode the current workload + constraints as a URL query string.
 * Only non-default values are emitted, so a fresh dashboard produces "".
 */
export function encodeStateToParams(
  workload: WorkloadInput,
  constraints: ConstraintInput,
): string {
  const params = new URLSearchParams();

  // Workload
  for (const key of Object.keys(DEFAULT_WORKLOAD) as (keyof WorkloadInput)[]) {
    const v = workload[key];
    const def = DEFAULT_WORKLOAD[key];
    if (isDefault(v, def)) continue;
    if (v === null || v === undefined) continue;
    params.set(key, String(v));
  }

  // Constraints (excluding metric_weights which is nested)
  const flatConstraintKeys: (keyof Omit<ConstraintInput, "metric_weights">)[] = [
    "max_budget_usd",
    "max_power_per_rack_kw",
    "cooling_type",
    "max_lead_time_weeks",
    "amortization_months",
    "colo_usd_per_kw_per_month",
    "hw_support_pct_of_capex_per_year",
    "software_usd_per_gpu_per_year",
  ];
  for (const key of flatConstraintKeys) {
    const v = constraints[key];
    const def = DEFAULT_CONSTRAINTS[key];
    if (isDefault(v, def)) continue;
    if (v === null || v === undefined) continue;
    params.set(key, String(v));
  }

  // Metric weights — encode as a single compact comma-separated value if any differ from defaults.
  const weightsDiffer = WEIGHT_KEYS.some(
    (k) => constraints.metric_weights[k] !== DEFAULT_CONSTRAINTS.metric_weights[k],
  );
  if (weightsDiffer) {
    // Encode as integer percentages: "35,30,15,20" → perf,cost,complexity,availability
    const csv = WEIGHT_KEYS.map((k) =>
      Math.round(constraints.metric_weights[k] * 100),
    ).join(",");
    params.set("weights", csv);
  }

  return params.toString();
}

/**
 * Decode a URL query string back into partial workload + constraint patches.
 * Missing keys mean "use the existing default"; we don't return full objects.
 */
export function decodeParamsToState(
  search: string,
): { workload: Partial<WorkloadInput>; constraints: Partial<ConstraintInput> } {
  const params = new URLSearchParams(search);
  const workload: Partial<WorkloadInput> = {};
  const constraints: Partial<ConstraintInput> = {};

  // Numeric workload fields
  const numericWorkload: (keyof WorkloadInput)[] = [
    "model_params_b",
    "context_length",
    "concurrent_users",
    "batch_size",
    "num_experts",
    "active_experts",
  ];
  for (const key of numericWorkload) {
    const v = params.get(key);
    if (v !== null && v !== "") {
      const n = Number(v);
      if (Number.isFinite(n)) (workload as Record<string, unknown>)[key] = n;
    }
  }

  // String / enum workload fields
  for (const key of ["precision", "workload_type", "finance_benchmark_category"] as const) {
    const v = params.get(key);
    if (v !== null) (workload as Record<string, unknown>)[key] = v;
  }

  // Boolean workload fields
  const isMoe = params.get("is_moe");
  if (isMoe !== null) workload.is_moe = isMoe === "true";

  // Numeric constraint fields (nullable: empty string clears, e.g. ?max_budget_usd=)
  const numericConstraints: (keyof ConstraintInput)[] = [
    "max_budget_usd",
    "max_power_per_rack_kw",
    "max_lead_time_weeks",
    "amortization_months",
    "colo_usd_per_kw_per_month",
    "hw_support_pct_of_capex_per_year",
    "software_usd_per_gpu_per_year",
  ];
  for (const key of numericConstraints) {
    const v = params.get(key);
    if (v !== null) {
      if (v === "") {
        (constraints as Record<string, unknown>)[key] = null;
      } else {
        const n = Number(v);
        if (Number.isFinite(n)) (constraints as Record<string, unknown>)[key] = n;
      }
    }
  }

  // String constraints
  const cooling = params.get("cooling_type");
  if (cooling !== null) constraints.cooling_type = cooling;

  // Metric weights (csv "35,30,15,20")
  const weights = params.get("weights");
  if (weights !== null) {
    const parts = weights.split(",").map((p) => Number(p) / 100);
    if (parts.length === 4 && parts.every((n) => Number.isFinite(n))) {
      constraints.metric_weights = {
        performance: parts[0],
        cost: parts[1],
        complexity: parts[2],
        availability: parts[3],
      };
    }
  }

  return { workload, constraints };
}
