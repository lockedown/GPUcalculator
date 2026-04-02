"use client";

import { useStore } from "@/lib/store";
import { WORKLOAD_CATEGORIES, PRECISION_OPTIONS, BENCHMARK_CATEGORIES } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Play, Loader2 } from "lucide-react";

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
  const { workload, setWorkload, runComparison, loading } = useStore();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Workload Configuration</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {/* Model Size */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-medium text-gray-500">Model Size (B params)</label>
            <Input
              type="number"
              min={1}
              max={2000}
              value={workload.model_params_b}
              onChange={(e) => setWorkload({ model_params_b: +e.target.value || 1 })}
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
            <Input
              type="number"
              min={1}
              max={100000}
              value={workload.concurrent_users}
              onChange={(e) => setWorkload({ concurrent_users: +e.target.value || 1 })}
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

        <Button onClick={runComparison} disabled={loading} className="mt-4" size="sm">
          {loading ? (
            <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Calculating…</>
          ) : (
            <><Play className="h-3.5 w-3.5" /> Run Comparison</>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
