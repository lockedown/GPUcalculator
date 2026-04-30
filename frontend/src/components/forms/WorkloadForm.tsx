"use client";

import { useStore } from "@/lib/store";
import { WORKLOAD_CATEGORIES, PRECISION_OPTIONS, BENCHMARK_CATEGORIES } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { NumericInput } from "@/components/ui/numeric-input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";

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
            <label className="text-[11px] font-medium text-gray-500">Model Size (B params)</label>
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
            <label className="text-[11px] font-medium text-gray-500">Precision</label>
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
            <label className="text-[11px] font-medium text-gray-500">Context Length</label>
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
            <label className="text-[11px] font-medium text-gray-500">Concurrent Users</label>
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
            <label className="text-[11px] font-medium text-gray-500">Workload Type</label>
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
            <label className="text-[11px] font-medium text-gray-500">Benchmark Category</label>
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
