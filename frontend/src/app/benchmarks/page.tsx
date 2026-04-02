"use client";

import BenchmarkMatrix from "@/components/charts/BenchmarkMatrix";

export default function BenchmarksPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Benchmark Matrix</h1>
        <p className="mt-1 text-sm text-gray-500">
          Finance GPU Benchmark Matrix — NVIDIA Hopper/Blackwell vs AMD Instinct across quantitative, risk, AI inference, HPC, trading, and tokenization workloads.
        </p>
      </div>
      <BenchmarkMatrix />
    </div>
  );
}
