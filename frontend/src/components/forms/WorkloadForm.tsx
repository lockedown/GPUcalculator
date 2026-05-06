"use client";

import { useStore } from "@/lib/store";
import {
  WORKLOAD_CATEGORIES,
  PRECISION_OPTIONS,
  BENCHMARK_CATEGORIES,
  MIG_PROFILE_OPTIONS,
  TENANCY_MODE_OPTIONS,
  SERVING_MODE_OPTIONS,
  type MigProfile,
  type TenancyMode,
  type ServingMode,
} from "@/types";
import { WORKLOAD_TEMPLATES } from "@/lib/workload-templates";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { NumericInput } from "@/components/ui/numeric-input";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loader2, Sparkles } from "lucide-react";

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
  const { workload, setWorkload, setConstraints, loading } = useStore();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Workload Configuration
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Template buttons — fill the form with a sensible starting point.
            Renders as a compact pill row above the inputs. */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
            <Sparkles className="h-3 w-3" /> Templates
          </span>
          {WORKLOAD_TEMPLATES.map((tpl) => (
            <Button
              key={tpl.id}
              variant="outline"
              size="sm"
              className="h-7 text-[10px] font-medium"
              title={tpl.blurb}
              onClick={() => {
                setWorkload(tpl.workload);
                if (tpl.constraints) setConstraints(tpl.constraints);
              }}
            >
              {tpl.label}
            </Button>
          ))}
        </div>

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

        {/* Multi-tenancy row */}
        <div className="mt-4 flex flex-wrap items-end gap-4 border-t border-gray-100 pt-4">
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="GPU Tenancy"
              tooltip={
                <>
                  <strong>Dedicated</strong> = one workload owns the GPU. <strong>MIG</strong> = NVIDIA hardware partitioning (Hopper only — H100/H200) — divides compute &amp; memory into instances; NVLink between instances is disabled. <strong>Run:ai fractional</strong> = software time-slicing — full GPU resources but per-tenant throughput is divided by N tenants, plus a small KV-fragmentation penalty.
                </>
              }
            />
            <Select
              value={workload.multi_tenancy_mode}
              onValueChange={(v) =>
                setWorkload({
                  multi_tenancy_mode: v as TenancyMode,
                  // Reset MIG profile when leaving MIG mode
                  mig_profile: v === "mig" ? workload.mig_profile ?? "1g.10gb" : null,
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TENANCY_MODE_OPTIONS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {workload.multi_tenancy_mode === "mig" && (
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
                MIG Profile
                <InfoTooltip>
                  Profile name follows the standard NVIDIA convention: <code>{`<compute_GIs>g.<memory_GB>`}</code>. The number after &quot;g&quot; is the GPC count out of 7; memory slices are 1/8ths of the HBM stack. Hopper GPUs (H100/H200) only.
                </InfoTooltip>
              </label>
              <Select
                value={workload.mig_profile ?? "1g.10gb"}
                onValueChange={(v) => setWorkload({ mig_profile: v as MigProfile })}
              >
                <SelectTrigger className="w-72">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MIG_PROFILE_OPTIONS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {workload.multi_tenancy_mode === "runai_fractional" && (
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
                Tenants per GPU
                <InfoTooltip>
                  Number of co-located tenants time-sharing one GPU. Each tenant&apos;s aggregate throughput = full-GPU throughput ÷ tenants. A 5% KV-fragmentation penalty is applied to reflect cache-eviction churn.
                </InfoTooltip>
              </label>
              <NumericInput
                min={2}
                max={32}
                fallback={2}
                value={workload.tenants}
                onChange={(v) => setWorkload({ tenants: v ?? 2 })}
                className="w-24"
              />
            </div>
          )}

          {workload.multi_tenancy_mode !== "dedicated" && (
            <span className="text-[10px] text-gray-400 pb-2 max-w-md">
              {workload.multi_tenancy_mode === "mig"
                ? "Sizing one tenant on one MIG slice. GPUs that don't support MIG (Blackwell, AMD, RTX) are filtered out with MIG_NOT_SUPPORTED."
                : `Each of ${workload.tenants} tenants gets aggregate ÷ ${workload.tenants} throughput. NVLink stays available, all memory accessible.`}
            </span>
          )}
        </div>

        {/* Serving mode (prefill / decode disaggregation) */}
        <div className="mt-4 flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1.5">
            <FieldLabel
              label="Serving Mode"
              tooltip={
                <>
                  <strong>Colocated</strong> = one GPU pool runs both prefill and decode (the default and most deployments). <strong>Disaggregated</strong> = separate pools per role, à la NVIDIA Dynamo / DeepSeek-V3 — prefill goes to compute-dense nodes, decode to bandwidth-dense nodes. v1 is observability-only: the recommended split is shown alongside the topology, cost / rack are still computed against the unified GPU count. Mostly worth it once you&apos;re deep in the production-inference regime (high concurrent users + long context).
                </>
              }
            />
            <Select
              value={workload.serving_mode}
              onValueChange={(v) => setWorkload({ serving_mode: v as ServingMode })}
            >
              <SelectTrigger className="min-w-[24rem]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SERVING_MODE_OPTIONS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {workload.serving_mode === "disaggregated" && (
            <span className="text-[10px] text-gray-400 pb-2 max-w-md">
              Showing a recommended 30/70 prefill/decode split as a hint. Sizing &amp; cost are still
              computed against the unified GPU count — heterogeneous SKUs per role land in v2.
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
