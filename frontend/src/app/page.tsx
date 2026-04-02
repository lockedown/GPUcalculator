"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";
import WorkloadForm from "@/components/forms/WorkloadForm";
import ConstraintSliders from "@/components/forms/ConstraintSliders";
import BubbleScatter from "@/components/charts/BubbleScatter";
import RadarChart from "@/components/charts/RadarChart";
import ComparisonTable from "@/components/charts/ComparisonTable";
import { Trophy, Cpu, Zap, Clock } from "lucide-react";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { GPU_COLORS } from "@/types";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Dashboard() {
  const { comparison, gpus, fetchGpus, runComparison, loading } = useStore();

  useEffect(() => {
    fetchGpus();
    runComparison();
  }, []);

  const results = comparison?.results ?? [];
  const sweetSpot = comparison?.sweet_spot_gpu ?? null;
  const topResult = results[0];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">GPU Deployment Optimizer</h1>
        <p className="mt-1 text-sm text-gray-500">
          Dynamic infrastructure sizing across NVIDIA Hopper/Blackwell and AMD Instinct — find the sweet spot for your workload.
        </p>
      </div>

      {/* Summary cards */}
      {!topResult && loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-4 w-20 mb-3" />
              <Skeleton className="h-7 w-28 mb-1" />
              <Skeleton className="h-3 w-16" />
            </Card>
          ))}
        </div>
      ) : topResult ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-amber-600">
              <Trophy className="h-3.5 w-3.5" /> Sweet Spot
            </div>
            <div className="mt-2 text-lg font-bold" style={{ color: GPU_COLORS[sweetSpot ?? ""] || "#111" }}>
              {sweetSpot}
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">
              Score: {topResult.composite_score?.toFixed(3)}
            </div>
          </Card>
          <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-blue-600">
              <Zap className="h-3.5 w-3.5" /> Best Performance
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {formatNumber(topResult.decode_tokens_per_sec)} tok/s
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">{topResult.gpu_name} decode</div>
          </Card>
          <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-emerald-600">
              <Cpu className="h-3.5 w-3.5" /> GPUs Required
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {topResult.topology?.gpu_count ?? "—"}×
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">{topResult.topology?.parallelism_strategy}</div>
          </Card>
          <Card className="border-violet-200 bg-gradient-to-br from-violet-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-violet-600">
              <Clock className="h-3.5 w-3.5" /> 36m TCO
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {formatCurrency(topResult.tco_gbp)}
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">{topResult.gpu_name}</div>
          </Card>
        </div>
      ) : null}

      {/* Config */}
      <WorkloadForm />
      <ConstraintSliders />

      {/* Visualizations */}
      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <BubbleScatter results={results} width={780} height={460} />
        <RadarChart results={results} />
      </div>

      {/* Table */}
      <ComparisonTable results={results} sweetSpot={sweetSpot} loading={loading && results.length === 0} />
    </div>
  );
}
