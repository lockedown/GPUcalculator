/**
 * Workload preset buttons for the dashboard. Each template is a partial set
 * of WorkloadInput + ConstraintInput overrides applied on top of the current
 * defaults — keeps the customer's existing region / OpEx settings intact while
 * snapping the workload-shape inputs to a sensible starting point.
 *
 * Use these as conversation-starters in customer meetings: "show me what
 * Chat at scale looks like on H200 vs B200" lands faster than building the
 * inputs from scratch every time.
 */

import type { ConstraintInput, WorkloadInput } from "@/types";

export interface WorkloadTemplate {
  id: string;
  label: string;
  blurb: string;
  workload: Partial<WorkloadInput>;
  constraints?: Partial<ConstraintInput>;
}

export const WORKLOAD_TEMPLATES: WorkloadTemplate[] = [
  {
    id: "chat-scale",
    label: "Chat at scale",
    blurb:
      "Llama-3-70B FP8, 4K context, 100 concurrent users. Production conversational inference; decode-bound.",
    workload: {
      model_params_b: 70,
      precision: "FP8",
      context_length: 4096,
      concurrent_users: 100,
      workload_type: "inference",
      batch_size: 1,
      is_moe: false,
      multi_tenancy_mode: "dedicated",
      serving_mode: "colocated",
    },
    constraints: {
      target_tpot_ms: 50,
    },
  },
  {
    id: "rag-enterprise",
    label: "RAG enterprise",
    blurb:
      "70B FP8, 32K context, 50 users. Long-context retrieval-augmented generation; prefill matters more than chat.",
    workload: {
      model_params_b: 70,
      precision: "FP8",
      context_length: 32768,
      concurrent_users: 50,
      workload_type: "inference",
      batch_size: 1,
      is_moe: false,
      multi_tenancy_mode: "dedicated",
      serving_mode: "disaggregated",
    },
    constraints: {
      target_tpot_ms: 100,
    },
  },
  {
    id: "training-run",
    label: "Training run",
    blurb:
      "405B BF16 fine-tuning, 8K context. Sized for the multi-node TP+PP regime; DLC-required GPUs come into play.",
    workload: {
      model_params_b: 405,
      precision: "BF16",
      context_length: 8192,
      concurrent_users: 1,
      workload_type: "fine-tuning",
      batch_size: 8,
      is_moe: false,
      multi_tenancy_mode: "dedicated",
      serving_mode: "colocated",
    },
    constraints: {
      cooling_type: "liquid",
      target_tpot_ms: null,
    },
  },
  {
    id: "quant-monte-carlo",
    label: "Quant Monte Carlo",
    blurb:
      "Risk / VaR Monte Carlo, FP64-bound. Routes to GPU FP64 ratings, finance benchmark category surfaces too.",
    workload: {
      model_params_b: 7,
      precision: "FP16",
      context_length: 4096,
      concurrent_users: 1,
      workload_type: "quant",
      batch_size: 1,
      is_moe: false,
      multi_tenancy_mode: "dedicated",
      serving_mode: "colocated",
      finance_benchmark_category: "quant",
    },
  },
];
