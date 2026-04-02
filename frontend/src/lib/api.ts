const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

import type {
  GPU,
  GPUDetail,
  BenchmarkWithGPU,
  NetworkingOption,
  GPUResult,
  ComparisonResponse,
  WorkloadInput,
  ConstraintInput,
  PriceHistoryByGPU,
} from "@/types";

export const api = {
  hardware: {
    list: (vendor?: string) =>
      fetchJSON<GPU[]>(`${API_BASE}/hardware${vendor ? `?vendor=${vendor}` : ""}`),
    get: (id: number) => fetchJSON<GPUDetail>(`${API_BASE}/hardware/${id}`),
  },
  benchmarks: {
    list: (params?: { category?: string; gpu_id?: number }) => {
      const sp = new URLSearchParams();
      if (params?.category) sp.set("category", params.category);
      if (params?.gpu_id) sp.set("gpu_id", String(params.gpu_id));
      const qs = sp.toString();
      return fetchJSON<BenchmarkWithGPU[]>(`${API_BASE}/benchmarks${qs ? `?${qs}` : ""}`);
    },
    byCategory: (category: string) =>
      fetchJSON<BenchmarkWithGPU[]>(`${API_BASE}/benchmarks/${category}`),
  },
  networking: {
    list: () => fetchJSON<NetworkingOption[]>(`${API_BASE}/networking`),
  },
  calculate: (workload: WorkloadInput, constraints?: ConstraintInput) =>
    fetchJSON<GPUResult[]>(`${API_BASE}/calculate`, {
      method: "POST",
      body: JSON.stringify({ workload, constraints }),
    }),
  compare: (workload: WorkloadInput, constraints?: ConstraintInput) =>
    fetchJSON<ComparisonResponse>(`${API_BASE}/compare`, {
      method: "POST",
      body: JSON.stringify(workload),
    }).catch(() =>
      // Fallback: try nested format if flat fails
      fetchJSON<ComparisonResponse>(`${API_BASE}/compare`, {
        method: "POST",
        body: JSON.stringify({ workload, constraints }),
      })
    ),
  prices: {
    list: () => fetchJSON<PriceHistoryByGPU[]>(`${API_BASE}/prices`),
    get: (gpuId: number) => fetchJSON<PriceHistoryByGPU>(`${API_BASE}/prices/${gpuId}`),
  },
};
