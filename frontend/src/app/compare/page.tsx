"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";
import WorkloadForm from "@/components/forms/WorkloadForm";
import ConstraintSliders from "@/components/forms/ConstraintSliders";
import BubbleScatter from "@/components/charts/BubbleScatter";
import RadarChart from "@/components/charts/RadarChart";
import ComparisonTable from "@/components/charts/ComparisonTable";

export default function ComparePage() {
  const { comparison, runComparison, loading } = useStore();

  useEffect(() => {
    if (!comparison) runComparison();
  }, []);

  const results = comparison?.results ?? [];
  const sweetSpot = comparison?.sweet_spot_gpu ?? null;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Compare GPUs</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your workload and constraints, then visualize the sweet spot across all GPU options.
        </p>
      </div>

      <WorkloadForm />
      <ConstraintSliders />

      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <BubbleScatter results={results} width={820} height={480} />
        <RadarChart results={results} />
      </div>

      <ComparisonTable results={results} sweetSpot={sweetSpot} loading={loading && results.length === 0} />
    </div>
  );
}
