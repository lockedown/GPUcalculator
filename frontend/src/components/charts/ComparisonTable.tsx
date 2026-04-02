"use client";

import Link from "next/link";
import type { GPUResult } from "@/types";
import { GPU_COLORS } from "@/types";
import { formatNumber, formatCurrency } from "@/lib/utils";
import { AlertTriangle, Trophy, ChevronRight, Download } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

function exportCSV(results: GPUResult[]) {
  const headers = [
    "Rank", "GPU", "Vendor", "Score",
    "Decode tok/s", "Prefill tok/s",
    "TCO (GBP)", "CapEx (GBP)", "OpEx/mo (GBP)", "Tokens/GBP/mo",
    "Complexity", "Availability",
    "GPU Count", "Nodes", "Strategy",
    "Racks", "Power/Rack (kW)", "PDU Tier",
    "Warnings",
  ];
  const rows = results.map((r, i) => [
    i + 1,
    r.gpu_name,
    r.gpu_vendor,
    r.composite_score?.toFixed(4) ?? "",
    r.decode_tokens_per_sec?.toFixed(0) ?? "",
    r.prefill_tokens_per_sec?.toFixed(0) ?? "",
    r.tco_gbp?.toFixed(0) ?? "",
    r.capex_gbp?.toFixed(0) ?? "",
    r.opex_monthly_gbp?.toFixed(0) ?? "",
    r.tokens_per_gbp?.toFixed(0) ?? "",
    r.complexity_score?.toFixed(2) ?? "",
    r.availability_score?.toFixed(2) ?? "",
    r.topology?.gpu_count ?? "",
    r.topology?.nodes ?? "",
    r.topology?.parallelism_strategy ?? "",
    r.rack_plan?.total_racks ?? "",
    r.rack_plan?.power_per_rack_kw ?? "",
    r.rack_plan?.pdu_tier_label ?? "",
    r.warnings.join("; "),
  ]);

  const csv = [headers, ...rows].map((row) =>
    row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")
  ).join("\n");

  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `gpu_comparison_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

interface Props {
  results: GPUResult[];
  sweetSpot: string | null;
  loading?: boolean;
}

export default function ComparisonTable({ results, sweetSpot, loading }: Props) {
  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle>Comparison Results</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (results.length === 0) {
    return (
      <Card>
        <CardContent className="flex h-32 items-center justify-center text-sm text-gray-400">
          Run a comparison to see results
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-center justify-between gap-4">
        <CardTitle>Comparison Results</CardTitle>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 text-[10px] h-7"
          onClick={() => exportCSV(results)}
        >
          <Download className="h-3 w-3" /> Export CSV
        </Button>
      </CardHeader>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-left text-xs">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50/80">
              <th className="px-4 py-3 font-semibold text-gray-500">#</th>
              <th className="px-4 py-3 font-semibold text-gray-500">GPU</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">Score</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">Decode tok/s</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">Prefill tok/s</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">TCO (36m)</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">Tokens/£/mo</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">Complexity</th>
              <th className="px-3 py-3 font-semibold text-gray-500 text-right">Availability</th>
              <th className="px-3 py-3 font-semibold text-gray-500">Topology</th>
              <th className="px-3 py-3 font-semibold text-gray-500">Warnings</th>
              <th className="px-3 py-3 w-8"></th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => {
              const isSweetSpot = r.gpu_name === sweetSpot;
              return (
                <tr
                  key={r.gpu_id}
                  className={`border-b border-gray-100 transition-colors hover:bg-blue-50/30 group ${isSweetSpot ? "bg-blue-50/40" : ""}`}
                >
                  <td className="px-4 py-2.5 font-mono text-gray-400 text-[10px]">{i + 1}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2.5 w-2.5 rounded-full flex-shrink-0 ring-2 ring-white shadow-sm"
                        style={{ backgroundColor: GPU_COLORS[r.gpu_name] || "#6b7280" }}
                      />
                      <span className="font-semibold text-gray-900">{r.gpu_name}</span>
                      {r.is_estimated && (
                        <Badge variant="outline" className="gap-1 text-orange-500 border-orange-200">
                          EST
                        </Badge>
                      )}
                      {isSweetSpot && (
                        <Badge variant="warning" className="gap-1">
                          <Trophy className="h-2.5 w-2.5" /> Sweet Spot
                        </Badge>
                      )}
                      <span className="text-[10px] text-gray-400">{r.gpu_vendor}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono font-semibold">
                    <span className={isSweetSpot ? "text-blue-700" : "text-gray-700"}>
                      {(r.composite_score ?? 0).toFixed(3)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-gray-700">
                    {formatNumber(r.decode_tokens_per_sec)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-gray-700">
                    {formatNumber(r.prefill_tokens_per_sec)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-gray-700">
                    {formatCurrency(r.tco_gbp)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-gray-700">
                    {formatNumber(r.tokens_per_gbp)}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <Badge variant={
                      (r.complexity_score ?? 0) >= 7 ? "success" :
                      (r.complexity_score ?? 0) >= 4 ? "warning" : "destructive"
                    }>
                      {r.complexity_score?.toFixed(1)}/10
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <span className="font-mono text-gray-600">
                      {((r.availability_score ?? 0) * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    {r.topology && (
                      <Badge variant="muted" className="font-mono">
                        {r.topology.gpu_count}× GPU · {r.topology.parallelism_strategy}
                      </Badge>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {r.warnings.length > 0 && (
                      <div className="flex items-start gap-1 text-amber-600">
                        <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
                        <span className="text-[10px] leading-tight">{r.warnings[0]}</span>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <Link
                      href={`/gpu/${r.gpu_id}`}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-blue-600"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
