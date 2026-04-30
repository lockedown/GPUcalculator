"use client";

import { useStore } from "@/lib/store";
import { WORKLOAD_CATEGORIES, PRECISION_OPTIONS, BENCHMARK_CATEGORIES } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { NumericInput } from "@/components/ui/numeric-input";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";

// Reusable label-with-tooltip — keeps the JSX below tidy.
function FieldLabel({
  label,
  tooltip,
  learnMore,
}: {
  label: string;
  tooltip: React.ReactNode;
  learnMore?: string;
}) {
  return (
    <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
      {label}
      <InfoTooltip learnMore={learnMore}>{tooltip}</InfoTooltip>
    </label>
  );
}

const CONTEXT_OPTIONS = [
  { value: 2048, label: "2K" },
  { value: 4096, label: "4K" },
  { value: 8192, label: "8K" },
  { value: 16384, label: "16K" },
  { value: 32768, label: "32K" },
  { value: 65536, label: "64K" },
  { value: 131072, label: "128K" },
];

export default function WorkloadForm() {
  const { workload, setWorkload, loading } = useStore();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Workload Configuration
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          {/* Model Size */}
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Model Size (B params)"
              learnMore="inputs"
              tooltip="Total parameter count in billions. Drives weight memory (params × bytes/precision) and decode throughput (memory-bandwidth-bound)."
            />
            <NumericInput
              min={1}
              max={2000}
              fallback={70}
              value={workload.model_params_b}
              onChange={(v) => setWorkload({ model_params_b: v ?? 1 })}
            />
          </div>

          {/* Precision */}
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Precision"
              learnMore="performance"
              tooltip="Numeric format at inference. FP16/BF16 = 2 B/param, FP8 = 1 B, FP4 = 0.5 B. Lower precision halves memory and roughly doubles throughput on supporting hardware."
            />
            <Select value={workload.precision} onValueChange={(v) => setWorkload({ precision: v })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRECISION_OPTIONS.map((p) => (
                  <SelectItem key={p} value={p}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Context Length */}
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Context Length"
              learnMore="topology"
              tooltip="Max input + output tokens per request. KV-cache memory grows linearly with context (~1.25 GiB/user at 4K, ~5 GiB at 16K for Llama-3-70B FP16)."
            />
            <Select
              value={String(workload.context_length)}
              onValueChange={(v) => setWorkload({ context_length: +v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CONTEXT_OPTIONS.map((c) => (
                  <SelectItem key={c.value} value={String(c.value)}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Concurrent Users */}
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Concurrent Users"
              learnMore="topology"
              tooltip="Independent requests in flight at once. Each user needs their own KV-cache slice. The engine adds DP replicas until every user can hit at least 10 tok/s."
            />
            <NumericInput
              min={1}
              max={100000}
              fallback={1}
              value={workload.concurrent_users}
              onChange={(v) => setWorkload({ concurrent_users: v ?? 1 })}
            />
          </div>

          {/* Workload Type */}
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Workload Type"
              learnMore="constraints"
              tooltip="Inference / training / fine-tuning / specialised finance categories. Acts as a hard filter — RTX PRO 6000 BSE is excluded from training jobs, for example."
            />
            <Select
              value={workload.workload_type}
              onValueChange={(v) => setWorkload({ workload_type: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WORKLOAD_CATEGORIES.map((w) => (
                  <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Finance Benchmark Category */}
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Benchmark Category"
              learnMore="performance"
              tooltip="If selected, blends the matching benchmark scores 50/50 with the roofline performance score so domain-specific strengths affect ranking."
            />
            <Select
              value={workload.finance_benchmark_category ?? "__none__"}
              onValueChange={(v) => setWorkload({ finance_benchmark_category: v === "__none__" ? null : v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">None</SelectItem>
                {BENCHMARK_CATEGORIES.map((c) => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* MoE row */}
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <label className="flex items-center gap-2 text-[11px] font-medium text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={workload.is_moe}
              onChange={(e) => setWorkload({ is_moe: e.target.checked })}
              className="rounded border-gray-300"
            />
            Mixture-of-Experts (MoE)
          </label>
          {workload.is_moe && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-medium text-gray-500">Total Experts</label>
                <NumericInput
                  min={2}
                  max={128}
                  fallback={8}
                  value={workload.num_experts}
                  onChange={(v) => setWorkload({ num_experts: v ?? 8 })}
                  className="w-20"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-medium text-gray-500">Active Experts</label>
                <NumericInput
                  min={1}
                  max={workload.num_experts}
                  fallback={2}
                  value={workload.active_experts}
                  onChange={(v) => setWorkload({ active_experts: v ?? 2 })}
                  className="w-20"
                />
              </div>
              <span className="text-[10px] text-gray-400 pb-2">
                {workload.active_experts}/{workload.num_experts} active — effective {((workload.active_experts / workload.num_experts) * workload.model_params_b).toFixed(0)}B params/token
              </span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
