"use client";

import { useEffect } from "react";
import { useStore } from "@/lib/store";
import { useUrlSync } from "@/lib/use-url-sync";
import WorkloadForm from "@/components/forms/WorkloadForm";
import ConstraintSliders from "@/components/forms/ConstraintSliders";
import BubbleScatter from "@/components/charts/BubbleScatter";
import SweetSpotDetail from "@/components/charts/SweetSpotDetail";
import ComparisonTable from "@/components/charts/ComparisonTable";
import { Trophy, Cpu, Zap, Banknote, Link as LinkIcon, Check, Pin, Printer } from "lucide-react";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { GPU_COLORS } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useState } from "react";
import { pinScenario, MAX_PINNED } from "@/lib/scenarios";
import Link from "next/link";

export default function Dashboard() {
  const { comparison, fetchGpus, runComparison, loading, constraints, workload } = useStore();
  useUrlSync(); // Two-way sync between URL ?params and store state
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchGpus();
    runComparison();
  }, []);

  async function copyShareLink() {
    if (typeof window === "undefined") return;
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      toast.success("Link copied", {
        description: "Anyone with this URL will see your exact configuration.",
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Couldn't copy — your browser blocked clipboard access.");
    }
  }

  function pinCurrentScenario() {
    const { workload, constraints } = useStore.getState();
    const result = pinScenario(workload, constraints);
    if (result === null) {
      toast.error(`Pin limit reached (${MAX_PINNED}). Remove one from /scenarios first.`);
      return;
    }
    toast.success("Scenario pinned", {
      description: `${result.length} of ${MAX_PINNED} pinned. Compare them on /scenarios.`,
      action: { label: "View", onClick: () => { window.location.href = "/scenarios"; } },
    });
  }

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
    const within = constraints.max_budget_usd ? " within budget" : "";
    return `${axes[0].label}${within}`;
  })();

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-gray-900">GPU Deployment Optimizer</h1>
          <p className="mt-1 text-sm text-gray-500">
            Dynamic infrastructure sizing across NVIDIA Hopper/Blackwell and AMD Instinct — find the sweet spot for your workload.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 print-hide">
          <Button
            variant="outline"
            size="sm"
            onClick={pinCurrentScenario}
            title={`Pin this configuration to compare side-by-side on /scenarios (max ${MAX_PINNED})`}
          >
            <Pin className="h-3.5 w-3.5" /> Pin scenario
          </Button>
          <Button asChild variant="ghost" size="sm" title="View pinned scenarios side-by-side">
            <Link href="/scenarios">Compare pins</Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={copyShareLink}
            title="Copy a link that reproduces this exact workload + constraints + weights"
          >
            {copied ? (
              <><Check className="h-3.5 w-3.5" /> Copied</>
            ) : (
              <><LinkIcon className="h-3.5 w-3.5" /> Copy share link</>
            )}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => typeof window !== "undefined" && window.print()}
            title="Print or save the current sweet-spot report as PDF"
          >
            <Printer className="h-3.5 w-3.5" /> Print / PDF
          </Button>
        </div>
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
              <InfoTooltip learnMore="weights">
                Highest composite score that passes all hard constraints. Falls back to top scorer if nothing passes (with violations flagged).
              </InfoTooltip>
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
              <InfoTooltip learnMore="performance">
                Aggregate tokens/sec across all DP replicas. Decode is memory-bandwidth-bound — calibrated against published Llama-3-70B benchmarks.
              </InfoTooltip>
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {formatNumber(sweetSpot.decode_tokens_per_sec)} tok/s
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">aggregate across GPUs</div>
          </Card>
          <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-emerald-600">
              <Cpu className="h-3.5 w-3.5" /> GPUs Required
              <InfoTooltip learnMore="topology">
                Sized to fit model + per-replica KV cache, then scale via DP replicas so each user can hit ≥10 tok/s. TP rounded to power of 2.
              </InfoTooltip>
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {sweetSpot.topology?.gpu_count ?? "—"}×
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">{sweetSpot.topology?.parallelism_strategy}</div>
          </Card>
          <Card className="border-violet-200 bg-gradient-to-br from-violet-50 to-white p-4">
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-widest text-violet-600">
              <Banknote className="h-3.5 w-3.5" /> {constraints.amortization_months / 12}-Year TCO
              <InfoTooltip learnMore="tco">
                CapEx (hardware + network) + OpEx (TDP × PUE × 730 h × $0.10/kWh, monthly) over the chosen amortisation period ({constraints.amortization_months} months). All figures in USD.
              </InfoTooltip>
            </div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {formatCurrency(sweetSpot.tco_usd)}
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">
              {formatNumber(sweetSpot.tokens_per_usd)} tok / $ / mo
            </div>
          </Card>
        </div>
      ) : null}

      {/* Config — interactive form, hidden in print */}
      <div className="print-hide">
        <WorkloadForm />
        <ConstraintSliders />
      </div>

      {/* Print-only: condensed snapshot of the inputs since the form is hidden */}
      <Card className="print-only print-break-avoid">
        <CardContent className="p-4 text-[11px]">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
            Configuration snapshot
          </div>
          <div className="grid grid-cols-3 gap-x-6 gap-y-1">
            <div><span className="text-gray-500">Model:</span> <strong>{workload.model_params_b}B</strong></div>
            <div><span className="text-gray-500">Precision:</span> <strong>{workload.precision}</strong></div>
            <div><span className="text-gray-500">Context:</span> <strong>{(workload.context_length / 1024).toFixed(0)}K</strong></div>
            <div><span className="text-gray-500">Concurrent users:</span> <strong>{workload.concurrent_users}</strong></div>
            <div><span className="text-gray-500">Workload:</span> <strong>{workload.workload_type}</strong></div>
            <div><span className="text-gray-500">Cooling:</span> <strong>{constraints.cooling_type}</strong></div>
            <div><span className="text-gray-500">Amortisation:</span> <strong>{constraints.amortization_months / 12} years</strong></div>
            <div><span className="text-gray-500">Max budget:</span> <strong>{constraints.max_budget_usd ? formatCurrency(constraints.max_budget_usd) : "—"}</strong></div>
            <div><span className="text-gray-500">Max lead time:</span> <strong>{constraints.max_lead_time_weeks ? `${constraints.max_lead_time_weeks} wk` : "—"}</strong></div>
            <div><span className="text-gray-500">Colo $/kW/mo:</span> <strong>${constraints.colo_usd_per_kw_per_month}</strong></div>
            <div><span className="text-gray-500">HW support %/yr:</span> <strong>{(constraints.hw_support_pct_of_capex_per_year * 100).toFixed(0)}%</strong></div>
            <div><span className="text-gray-500">Software $/GPU/yr:</span> <strong>${constraints.software_usd_per_gpu_per_year}</strong></div>
            <div className="col-span-3 mt-1">
              <span className="text-gray-500">Weights:</span>{" "}
              perf {(constraints.metric_weights.performance * 100).toFixed(0)}% ·
              cost {(constraints.metric_weights.cost * 100).toFixed(0)}% ·
              complexity {(constraints.metric_weights.complexity * 100).toFixed(0)}% ·
              availability {(constraints.metric_weights.availability * 100).toFixed(0)}%
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Visualisations — BubbleScatter is screen-only; SweetSpotDetail prints */}
      <div className="grid gap-5 xl:grid-cols-[1fr_400px]">
        <div className="print-hide">
          <BubbleScatter results={results} width={780} height={460} />
        </div>
        <div className="print-break-avoid">
          <SweetSpotDetail result={sweetSpot} loading={loading && !sweetSpot} />
        </div>
      </div>

      {/* Table — included in print */}
      <ComparisonTable results={results} sweetSpot={sweetSpotName} loading={loading && results.length === 0} />

      {/* Print-only footer */}
      <div className="print-only mt-4 text-[9px] text-gray-500">
        Generated by gpu-calc.vercel.app · Methodology: gpu-calc.vercel.app/methodology
      </div>
    </div>
  );
}
