import { describe, expect, it } from "vitest";
import type { ConstraintInput, WorkloadInput } from "@/types";
import { DEFAULT_CONSTRAINTS, DEFAULT_WORKLOAD } from "./defaults";
import { decodeParamsToState, encodeStateToParams } from "./url-state";

describe("url-state share links", () => {
  it("emits nothing for the defaults", () => {
    expect(encodeStateToParams(DEFAULT_WORKLOAD, DEFAULT_CONSTRAINTS)).toBe("");
  });

  it("round-trips a changed workload and constraints", () => {
    const workload: WorkloadInput = {
      ...DEFAULT_WORKLOAD,
      model_params_b: 405,
      precision: "FP8",
      is_moe: true,
      serving_mode: "disaggregated",
    };
    const constraints: ConstraintInput = {
      ...DEFAULT_CONSTRAINTS,
      max_budget_usd: 5_000_000,
      cooling_type: "liquid",
      metric_weights: { performance: 0.5, cost: 0.2, complexity: 0.1, availability: 0.2 },
    };
    const decoded = decodeParamsToState(encodeStateToParams(workload, constraints));
    expect({ ...DEFAULT_WORKLOAD, ...decoded.workload }).toEqual(workload);
    expect({ ...DEFAULT_CONSTRAINTS, ...decoded.constraints }).toEqual(constraints);
  });

  it("ignores non-numeric values instead of passing NaN to the API", () => {
    const { workload } = decodeParamsToState("model_params_b=abc&concurrent_users=Infinity");
    expect(workload).toEqual({});
  });
});
