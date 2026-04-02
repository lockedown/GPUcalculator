/**
 * Server-side API helpers for ISR data fetching.
 * These use Next.js `fetch` with `next.revalidate` for edge caching.
 */

import type { GPU, BenchmarkWithGPU } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

export async function fetchAllGPUs(): Promise<GPU[]> {
  const res = await fetch(`${API_BASE}/hardware`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchAllBenchmarks(): Promise<BenchmarkWithGPU[]> {
  const res = await fetch(`${API_BASE}/benchmarks`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) return [];
  return res.json();
}
