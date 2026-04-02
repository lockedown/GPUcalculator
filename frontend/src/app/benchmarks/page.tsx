import { fetchAllGPUs, fetchAllBenchmarks } from "@/lib/server-api";
import BenchmarkMatrix from "@/components/charts/BenchmarkMatrix";

export const revalidate = 300;

export default async function BenchmarksPage() {
  const [benchmarks, gpus] = await Promise.all([
    fetchAllBenchmarks(),
    fetchAllGPUs(),
  ]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Benchmark Matrix</h1>
        <p className="mt-1 text-sm text-gray-500">
          Finance GPU Benchmark Matrix — NVIDIA Hopper/Blackwell vs AMD Instinct across quantitative, risk, AI inference, HPC, trading, and tokenization workloads.
        </p>
      </div>
      <BenchmarkMatrix initialBenchmarks={benchmarks} initialGpus={gpus} />
    </div>
  );
}
