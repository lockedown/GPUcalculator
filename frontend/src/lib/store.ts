import { create } from "zustand";
import type {
  WorkloadInput,
  ConstraintInput,
  ComparisonResponse,
  GPU,
  BenchmarkWithGPU,
} from "@/types";
import { api } from "./api";
import { toast } from "sonner";

interface AppState {
  // Data
  gpus: GPU[];
  benchmarks: BenchmarkWithGPU[];
  comparison: ComparisonResponse | null;

  // Workload config
  workload: WorkloadInput;
  constraints: ConstraintInput;

  // UI state
  loading: boolean;
  error: string | null;
  selectedGpuId: number | null;
  benchmarkCategory: string | null;

  // Actions
  setWorkload: (w: Partial<WorkloadInput>) => void;
  setConstraints: (c: Partial<ConstraintInput>) => void;
  setMetricWeight: (key: string, value: number) => void;
  setSelectedGpuId: (id: number | null) => void;
  setBenchmarkCategory: (cat: string | null) => void;
  fetchGpus: () => Promise<void>;
  fetchBenchmarks: (category?: string) => Promise<void>;
  runComparison: () => Promise<void>;
}

// Debounce helper — delays execution until idle for `ms` milliseconds.
// 250 ms feels live without flooding the API while a slider is being dragged.
let _debounceTimer: ReturnType<typeof setTimeout> | null = null;
function debouncedCompare(fn: () => void, ms = 250) {
  if (_debounceTimer) clearTimeout(_debounceTimer);
  _debounceTimer = setTimeout(fn, ms);
}

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
  metric_weights: {
    performance: 0.35,
    cost: 0.3,
    complexity: 0.15,
    availability: 0.2,
  },
};

export const useStore = create<AppState>((set, get) => ({
  gpus: [],
  benchmarks: [],
  comparison: null,
  workload: { ...DEFAULT_WORKLOAD },
  constraints: { ...DEFAULT_CONSTRAINTS },
  loading: false,
  error: null,
  selectedGpuId: null,
  benchmarkCategory: null,

  setWorkload: (w) => {
    set((s) => ({ workload: { ...s.workload, ...w } }));
    debouncedCompare(() => get().runComparison());
  },

  setConstraints: (c) => {
    set((s) => ({ constraints: { ...s.constraints, ...c } }));
    debouncedCompare(() => get().runComparison());
  },

  setMetricWeight: (key, value) => {
    set((s) => ({
      constraints: {
        ...s.constraints,
        metric_weights: { ...s.constraints.metric_weights, [key]: value },
      },
    }));
    debouncedCompare(() => get().runComparison());
  },

  setSelectedGpuId: (id) => set({ selectedGpuId: id }),

  setBenchmarkCategory: (cat) => set({ benchmarkCategory: cat }),

  fetchGpus: async () => {
    try {
      const gpus = await api.hardware.list();
      set({ gpus });
    } catch (e) {
      const msg = (e as Error).message;
      set({ error: msg });
      toast.error("Failed to load GPUs", { description: msg });
    }
  },

  fetchBenchmarks: async (category?: string) => {
    try {
      const benchmarks = await api.benchmarks.list(
        category ? { category } : undefined
      );
      set({ benchmarks, benchmarkCategory: category ?? null });
    } catch (e) {
      const msg = (e as Error).message;
      set({ error: msg });
      toast.error("Failed to load benchmarks", { description: msg });
    }
  },

  runComparison: async () => {
    const { workload, constraints } = get();
    set({ loading: true, error: null });
    try {
      const comparison = await api.compare(workload, constraints);
      set({ comparison, loading: false });
    } catch (e) {
      const msg = (e as Error).message;
      set({ error: msg, loading: false });
      toast.error("Comparison failed", { description: msg });
    }
  },
}));
