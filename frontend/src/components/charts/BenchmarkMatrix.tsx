"use client";

import { Fragment, useEffect, useState } from "react";
import type { BenchmarkWithGPU, GPU } from "@/types";
import { GPU_COLORS, BENCHMARK_CATEGORIES } from "@/types";
import { ratingColor, cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

const GPU_ORDER = [
  "H200 SXM5", "B100 SXM", "B200 SXM", "B300 SXM", "GB200 NVL72", "GB300 NVL72",
  "MI300X", "MI350X", "MI355X",
];

interface MatrixRow {
  benchmark_name: string;
  workload_category: string;
  workload_description: string;
  cells: Record<string, BenchmarkWithGPU>;
}

export default function BenchmarkMatrix() {
  const [benchmarks, setBenchmarks] = useState<BenchmarkWithGPU[]>([]);
  const [gpus, setGpus] = useState<GPU[]>([]);
  const [category, setCategory] = useState<string | null>(null);
  const [showNvidia, setShowNvidia] = useState(true);
  const [showAmd, setShowAmd] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.benchmarks.list(category ? { category } : undefined),
      api.hardware.list(),
    ]).then(([b, g]) => {
      setBenchmarks(b);
      setGpus(g);
      setLoading(false);
    });
  }, [category]);

  // Build matrix rows
  const rows: MatrixRow[] = [];
  const seen = new Set<string>();
  for (const b of benchmarks) {
    const key = `${b.workload_category}::${b.benchmark_name}`;
    if (!seen.has(key)) {
      seen.add(key);
      rows.push({
        benchmark_name: b.benchmark_name,
        workload_category: b.workload_category,
        workload_description: b.workload_description || "",
        cells: {},
      });
    }
    const row = rows.find(
      (r) => r.benchmark_name === b.benchmark_name && r.workload_category === b.workload_category
    );
    if (row && b.gpu_name) {
      row.cells[b.gpu_name] = b;
    }
  }

  // Group rows by category
  const grouped: Record<string, MatrixRow[]> = {};
  for (const row of rows) {
    if (!grouped[row.workload_category]) grouped[row.workload_category] = [];
    grouped[row.workload_category].push(row);
  }

  const visibleGpus = GPU_ORDER.filter((name) => {
    const gpu = gpus.find((g) => g.name === name);
    if (!gpu) return false;
    if (gpu.vendor === "NVIDIA" && !showNvidia) return false;
    if (gpu.vendor === "AMD" && !showAmd) return false;
    return true;
  });

  const nvCount = visibleGpus.filter((n) => {
    const g = gpus.find((x) => x.name === n);
    return g?.vendor === "NVIDIA";
  }).length;
  const amdCount = visibleGpus.length - nvCount;

  if (loading) {
    return (
      <Card>
        <CardContent className="space-y-3 p-5">
          <Skeleton className="h-6 w-48" />
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <div>
      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 mr-1">Workload:</span>
        <Button
          variant={!category ? "default" : "outline"}
          size="sm"
          onClick={() => setCategory(null)}
          className="text-[10px] uppercase tracking-wide h-7"
        >
          All
        </Button>
        {BENCHMARK_CATEGORIES.map((c) => (
          <Button
            key={c.value}
            variant={category === c.value ? "default" : "outline"}
            size="sm"
            onClick={() => setCategory(c.value)}
            className="text-[10px] uppercase tracking-wide h-7"
          >
            {c.label}
          </Button>
        ))}

        <span className="ml-3 h-5 w-px bg-gray-200" />
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 ml-1 mr-1">Vendor:</span>
        <Button
          variant={showNvidia ? "default" : "outline"}
          size="sm"
          onClick={() => setShowNvidia(!showNvidia)}
          className={cn("text-[10px] uppercase tracking-wide h-7", showNvidia && "bg-green-600 hover:bg-green-700")}
        >
          NVIDIA
        </Button>
        <Button
          variant={showAmd ? "default" : "outline"}
          size="sm"
          onClick={() => setShowAmd(!showAmd)}
          className={cn("text-[10px] uppercase tracking-wide h-7", showAmd && "bg-red-600 hover:bg-red-700")}
        >
          AMD
        </Button>
      </div>

      {/* Table */}
      <Card className="overflow-x-auto overflow-hidden">
        <table className="w-full min-w-[1200px] border-collapse text-xs">
          <thead>
            {/* Vendor header */}
            <tr className="border-b border-gray-300">
              <th colSpan={2} className="bg-gray-50 px-3 py-2" />
              {nvCount > 0 && (
                <th
                  colSpan={nvCount}
                  className="bg-green-50/50 px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-widest text-green-700 border-l border-green-200"
                >
                  NVIDIA — Hopper / Blackwell
                </th>
              )}
              {amdCount > 0 && (
                <th
                  colSpan={amdCount}
                  className="bg-red-50/50 px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-widest text-red-700 border-l-2 border-red-200"
                >
                  AMD — Instinct MI Series
                </th>
              )}
            </tr>
            {/* GPU names */}
            <tr className="border-b-2 border-gray-300 bg-gray-50/80">
              <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-gray-500 min-w-[160px]">
                Benchmark
              </th>
              <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-gray-500 min-w-[160px]">
                Workload
              </th>
              {visibleGpus.map((name) => {
                const isAmd = gpus.find((g) => g.name === name)?.vendor === "AMD";
                const isFirstAmd = isAmd && visibleGpus.indexOf(name) === nvCount;
                return (
                  <th
                    key={name}
                    className={cn(
                      "px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-wide min-w-[105px]",
                      isFirstAmd ? "border-l-2 border-red-200" : "border-l border-gray-200"
                    )}
                    style={{ color: GPU_COLORS[name] }}
                  >
                    {name}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {Object.entries(grouped).map(([cat, catRows]) => (
              <Fragment key={cat}>
                {/* Section header */}
                {!category && (
                  <tr className="border-t-2 border-gray-200 bg-gray-50">
                    <td
                      colSpan={2 + visibleGpus.length}
                      className="px-3 py-2 text-[10px] font-semibold uppercase tracking-widest text-violet-600"
                    >
                      {BENCHMARK_CATEGORIES.find((c) => c.value === cat)?.label || cat}
                    </td>
                  </tr>
                )}
                {catRows.map((row) => (
                  <tr key={`${cat}-${row.benchmark_name}`} className="border-b border-gray-100 hover:bg-blue-50/20 transition-colors">
                    <td className="px-3 py-2.5 font-medium text-gray-900 whitespace-nowrap">
                      {row.benchmark_name}
                    </td>
                    <td className="px-3 py-2.5 text-[11px] text-gray-500 max-w-[200px] leading-snug">
                      {row.workload_description.slice(0, 100)}
                    </td>
                    {visibleGpus.map((gpuName) => {
                      const cell = row.cells[gpuName];
                      const isAmd = gpus.find((g) => g.name === gpuName)?.vendor === "AMD";
                      const isFirstAmd = isAmd && visibleGpus.indexOf(gpuName) === nvCount;
                      if (!cell) {
                        return (
                          <td
                            key={gpuName}
                            className={cn("px-2 py-2 text-center", isFirstAmd ? "border-l-2 border-red-200" : "border-l border-gray-100")}
                          >
                            <span className="text-gray-300">—</span>
                          </td>
                        );
                      }
                      return (
                        <td
                          key={gpuName}
                          className={cn(
                            "px-2 py-2 text-center",
                            isFirstAmd ? "border-l-2 border-red-200" : "border-l border-gray-100"
                          )}
                        >
                          <div className="flex flex-col items-center gap-1">
                            <span
                              className={cn(
                                "inline-block rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide border",
                                ratingColor(cell.rating)
                              )}
                            >
                              {cell.rating}
                            </span>
                            {cell.bar_pct != null && (
                              <div className="h-[3px] w-16 rounded-full bg-gray-100 overflow-hidden">
                                <div
                                  className="h-full rounded-full transition-all duration-700"
                                  style={{
                                    width: `${cell.bar_pct}%`,
                                    backgroundColor: GPU_COLORS[gpuName] || "#6b7280",
                                  }}
                                />
                              </div>
                            )}
                            {cell.metric_value && (
                              <span className="text-[9px] font-mono text-gray-400">
                                {cell.metric_value}
                              </span>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
