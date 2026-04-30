"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";
import WorkloadForm from "@/components/forms/WorkloadForm";
import ConstraintSliders from "@/components/forms/ConstraintSliders";
import BubbleScatter from "@/components/charts/BubbleScatter";
import SweetSpotDetail from "@/components/charts/SweetSpotDetail";
import ComparisonTable from "@/components/charts/ComparisonTable";
import { Trophy, Cpu, Zap, Banknote } from "lucide-react";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { GPU_COLORS } from "@/types";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function Dashboard() {
  const { comparison, fetchGpus, runComparison, loading, constraints } = useStore();

  useEffect(() => {
    fetchGpus();
    runComparison();
  }, []);

  const results = comparison?.results ?? [];
  const sweetSpotName = comparison?.sweet_spot_gpu ?? null;
  const sweetSpot =
    results.find((r) => r.gpu_name === sweetSpotName) ?? results[0] ?? null;

  // Pick the dominant axis from the metric weights to label the recommendation.
  const reasonLabel = (() => {
    if (!sweetSpot) return null;
    const w = constraints.metric_weights;
    const axes: { key: string; label: string; w: number }[] = [
      { key: "performance", label: "best performance", w: w.performance },
      { key: "cost", label: "lowest TCO", w: w.cost },
      { key: "complexity", label: "simplest stack", w: w.complexity },
      { key: "availability", label: "fastest delivery", w: w.availability },
    ];
    axes.sort((a, b) => b.w - a.w);
    const within = constraints.max_budget_gbp ? " within budget" : "";
    return `${axes[0].label}${within}`;
  })();

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
      {!sweetSpot && loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-4 w-20 mb-3" />
              <Skeleton className="h-7 w-28 mb-1" />
              <Skeleton className="h-3 w-16" />
            </Card>
          ))}
        </div>
      ) : sweetSpot ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-amber-600">
              <Trophy className="h-3.5 w-3.5" /> Sweet Spot
            </div>
            <div className="mt-2 text-lg font-bold" style={{ color: GPU_COLORS[sweetSpot.gpu_name] || "#111" }}>
              {sweetSpot.gpu_name}
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">
              {reasonLabel}
            </div>
          </Card>
          <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-blue-600">
              <Zap className="h-3.5 w-3.5" /> Decode Throughput
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {formatNumber(sweetSpot.decode_tokens_per_sec)} tok/s
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">aggregate across GPUs</div>
          </Card>
          <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-emerald-600">
              <Cpu className="h-3.5 w-3.5" /> GPUs Required
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {sweetSpot.topology?.gpu_count ?? "—"}×
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">{sweetSpot.topology?.parallelism_strategy}</div>
          </Card>
          <Card className="border-violet-200 bg-gradient-to-br from-violet-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-violet-600">
              <Banknote className="h-3.5 w-3.5" /> 36-month TCO
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {formatCurrency(sweetSpot.tco_gbp)}
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">
              {formatNumber(sweetSpot.tokens_per_gbp)} tok / £ / mo
            </div>
          </Card>
        </div>
      ) : null}

      {/* Config */}
      <WorkloadForm />
      <ConstraintSliders />

      {/* Visualisations: BubbleScatter + SweetSpotDetail panel */}
      <div className="grid gap-5 xl:grid-cols-[1fr_400px]">
        <BubbleScatter results={results} width={780} height={460} />
        <SweetSpotDetail result={sweetSpot} loading={loading && !sweetSpot} />
      </div>

      {/* Table */}
      <ComparisonTable results={results} sweetSpot={sweetSpotName} loading={loading && results.length === 0} />
    </div>
  );
}
