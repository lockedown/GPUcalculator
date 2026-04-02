"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} from "recharts";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import type { GPUDetail, GPUResult, BenchmarkScore } from "@/types";
import { GPU_COLORS, BENCHMARK_CATEGORIES } from "@/types";
import { formatNumber, formatCurrency, ratingColor } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  ArrowLeft,
  Cpu,
  Zap,
  DollarSign,
  Layers,
  Droplets,
  Wind,
  AlertTriangle,
  Trophy,
  Server,
  Network,
} from "lucide-react";
import { toast } from "sonner";

export default function GPUDeepDivePage() {
  const params = useParams();
  const router = useRouter();
  const gpuId = Number(params.id);

  const [gpu, setGpu] = useState<GPUDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const { comparison, runComparison } = useStore();

  useEffect(() => {
    setLoading(true);
    api.hardware
      .get(gpuId)
      .then(setGpu)
      .catch((e) => {
        toast.error("GPU not found", { description: (e as Error).message });
        router.push("/hardware");
      })
      .finally(() => setLoading(false));

    if (!comparison) runComparison();
  }, [gpuId]);

  const gpuResult: GPUResult | undefined = comparison?.results.find(
    (r) => r.gpu_id === gpuId
  );
  const isSweetSpot = comparison?.sweet_spot_gpu === gpu?.name;
  const color = GPU_COLORS[gpu?.name ?? ""] || "#6b7280";

  if (loading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5"><Skeleton className="h-20 w-full" /></Card>
          ))}
        </div>
        <Card className="p-5"><Skeleton className="h-80 w-full" /></Card>
      </div>
    );
  }

  if (!gpu) return null;

  // Group benchmarks by category
  const benchmarksByCategory = gpu.benchmarks.reduce<Record<string, BenchmarkScore[]>>(
    (acc, b) => {
      const cat = b.workload_category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(b);
      return acc;
    },
    {}
  );

  // Benchmark bar chart data
  const barData = gpu.benchmarks
    .filter((b) => b.bar_pct != null)
    .map((b) => ({
      name: b.benchmark_name.length > 25 ? b.benchmark_name.slice(0, 25) + "…" : b.benchmark_name,
      fullName: b.benchmark_name,
      score: b.bar_pct ?? 0,
      rating: b.rating,
      metric: b.metric_value,
    }))
    .sort((a, b) => b.score - a.score);

  // Radar data from comparison metrics (if available)
  const radarData = gpuResult
    ? [
        { metric: "Performance", value: normalize(gpuResult.decode_tokens_per_sec, comparison?.results.map((r) => r.decode_tokens_per_sec ?? 0) ?? []) },
        { metric: "Cost Efficiency", value: normalize(gpuResult.tco_gbp, comparison?.results.map((r) => r.tco_gbp ?? 0) ?? [], true) },
        { metric: "Simplicity", value: normalize(gpuResult.complexity_score, comparison?.results.map((r) => r.complexity_score ?? 0) ?? []) },
        { metric: "Availability", value: normalize(gpuResult.availability_score, comparison?.results.map((r) => r.availability_score ?? 0) ?? []) },
      ]
    : [];

  // Cost breakdown data
  const costData = gpuResult
    ? [
        { name: "CapEx", value: gpuResult.capex_gbp ?? 0, fill: "#3b82f6" },
        { name: "OpEx (36m)", value: (gpuResult.opex_monthly_gbp ?? 0) * 36, fill: "#10b981" },
        { name: "Network (est.)", value: Math.max(0, (gpuResult.tco_gbp ?? 0) - (gpuResult.capex_gbp ?? 0) - (gpuResult.opex_monthly_gbp ?? 0) * 36), fill: "#8b5cf6" },
      ]
    : [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()} className="mt-1">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
            <h1 className="text-2xl font-bold tracking-tight" style={{ color }}>
              {gpu.name}
            </h1>
            {isSweetSpot && (
              <Badge variant="warning" className="gap-1">
                <Trophy className="h-3 w-3" /> Sweet Spot
              </Badge>
            )}
            {gpu.is_estimated && <Badge variant="warning">Estimated Specs</Badge>}
          </div>
          <p className="mt-1 text-sm text-gray-500">
            {gpu.vendor} · {gpu.generation} · {gpu.form_factor}
            {gpu.cooling_type === "liquid" ? " · Liquid Cooled" : " · Air Cooled"}
          </p>
        </div>
      </div>

      {/* Quick stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <StatCard icon={<Cpu className="h-4 w-4" />} label="HBM" value={`${gpu.hbm_capacity_gb}GB`} sub={gpu.hbm_type ?? ""} />
        <StatCard icon={<Zap className="h-4 w-4" />} label="Mem BW" value={`${gpu.mem_bandwidth_tb_s} TB/s`} />
        <StatCard icon={<Layers className="h-4 w-4" />} label="BF16" value={gpu.bf16_tflops ? `${formatNumber(gpu.bf16_tflops)} TF` : "—"} />
        <StatCard icon={<Layers className="h-4 w-4" />} label="FP8" value={gpu.fp8_tflops ? `${formatNumber(gpu.fp8_tflops)} TF` : "N/A"} />
        <StatCard icon={<Zap className="h-4 w-4" />} label="TDP" value={gpu.tdp_watts ? `${gpu.tdp_watts}W` : "—"} />
        <StatCard icon={<DollarSign className="h-4 w-4" />} label="MSRP" value={gpu.msrp_usd ? `$${gpu.msrp_usd.toLocaleString()}` : "—"} />
      </div>

      {/* Main content grid */}
      <div className="grid gap-5 lg:grid-cols-[1fr_400px]">
        {/* Left column: Benchmarks */}
        <div className="space-y-5">
          {/* Benchmark bar chart */}
          <Card>
            <CardHeader>
              <CardTitle>Benchmark Scores</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {barData.length > 0 ? (
                <ResponsiveContainer width="100%" height={Math.max(300, barData.length * 28)}>
                  <BarChart data={barData} layout="vertical" margin={{ left: 120, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#6b7280" }} width={120} />
                    <Tooltip
                      formatter={(value, _name, props) => [
                        `${value}% — ${(props.payload as Record<string, string>).rating ?? ""} ${(props.payload as Record<string, string>).metric ? `(${(props.payload as Record<string, string>).metric})` : ""}`,
                        (props.payload as Record<string, string>).fullName,
                      ]}
                      contentStyle={{ fontSize: "11px", borderRadius: "8px", border: "1px solid #e5e7eb" }}
                    />
                    <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                      {barData.map((_, i) => (
                        <Cell key={i} fill={color} fillOpacity={0.75 - i * 0.02} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 py-8 text-center">No benchmark data available</p>
              )}
            </CardContent>
          </Card>

          {/* Benchmark details by category */}
          <Card>
            <CardHeader>
              <CardTitle>Benchmark Details</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <Tabs defaultValue={Object.keys(benchmarksByCategory)[0] ?? "all"}>
                <TabsList className="flex-wrap h-auto gap-1">
                  {Object.keys(benchmarksByCategory).map((cat) => (
                    <TabsTrigger key={cat} value={cat} className="capitalize">
                      {BENCHMARK_CATEGORIES.find((c) => c.value === cat)?.label ?? cat}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {Object.entries(benchmarksByCategory).map(([cat, benchmarks]) => (
                  <TabsContent key={cat} value={cat}>
                    <div className="space-y-2">
                      {benchmarks.map((b) => (
                        <div
                          key={b.id}
                          className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50/50 p-3"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-gray-900 truncate">{b.benchmark_name}</div>
                            {b.workload_description && (
                              <div className="text-[10px] text-gray-400 truncate">{b.workload_description}</div>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                            {b.metric_value && (
                              <span className="font-mono text-[10px] text-gray-600">{b.metric_value}</span>
                            )}
                            {b.rating && (
                              <Badge className={cn("text-[9px]", ratingColor(b.rating))}>
                                {b.rating}
                              </Badge>
                            )}
                            {b.bar_pct != null && (
                              <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full"
                                  style={{ width: `${b.bar_pct}%`, backgroundColor: color }}
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        </div>

        {/* Right column: Radar, Topology, Cost */}
        <div className="space-y-5">
          {/* Radar chart */}
          {radarData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Multi-Metric Profile</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <ResponsiveContainer width="100%" height={280}>
                  <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                    <PolarGrid stroke="#e5e7eb" />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: "#6b7280" }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar
                      name={gpu.name}
                      dataKey="value"
                      stroke={color}
                      fill={color}
                      fillOpacity={0.2}
                      strokeWidth={2}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: "11px", borderRadius: "8px", border: "1px solid #e5e7eb" }}
                      formatter={(value) => [`${Number(value).toFixed(0)}`, ""]}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Topology */}
          {gpuResult?.topology && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Server className="h-3.5 w-3.5 text-gray-400" /> Topology
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Total GPUs</span>
                    <span className="font-mono text-sm font-bold text-gray-900">{gpuResult.topology.gpu_count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Nodes</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.topology.nodes}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">GPUs/Node</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.topology.gpus_per_node}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Strategy</span>
                    <Badge variant="muted" className="font-mono">{gpuResult.topology.parallelism_strategy}</Badge>
                  </div>
                  <div className="border-t border-gray-100 pt-3 grid grid-cols-3 gap-2 text-center">
                    <div>
                      <div className="text-[9px] uppercase tracking-widest text-gray-400">TP</div>
                      <div className="font-mono text-lg font-bold text-blue-600">{gpuResult.topology.tp_degree}</div>
                    </div>
                    <div>
                      <div className="text-[9px] uppercase tracking-widest text-gray-400">PP</div>
                      <div className="font-mono text-lg font-bold text-emerald-600">{gpuResult.topology.pp_degree}</div>
                    </div>
                    <div>
                      <div className="text-[9px] uppercase tracking-widest text-gray-400">DP</div>
                      <div className="font-mono text-lg font-bold text-violet-600">{gpuResult.topology.dp_degree}</div>
                    </div>
                  </div>
                  {gpuResult.topology.cross_node_latency_penalty > 0 && (
                    <div className="flex items-center gap-2 rounded-md bg-amber-50 border border-amber-200 p-2 text-[10px] text-amber-700">
                      <Network className="h-3.5 w-3.5 flex-shrink-0" />
                      Cross-node latency penalty: {(gpuResult.topology.cross_node_latency_penalty * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Rack Plan */}
          {gpuResult?.rack_plan && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Server className="h-3.5 w-3.5 text-gray-400" /> Rack Plan
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-center border-b border-gray-100 pb-3">
                    <div>
                      <div className="text-[9px] uppercase tracking-widest text-gray-400">Racks</div>
                      <div className="font-mono text-lg font-bold text-gray-900">{gpuResult.rack_plan.total_racks}</div>
                    </div>
                    <div>
                      <div className="text-[9px] uppercase tracking-widest text-gray-400">GPUs/Rack</div>
                      <div className="font-mono text-lg font-bold text-gray-900">{gpuResult.rack_plan.gpus_per_rack}</div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">PDU Tier</span>
                    <Badge variant="muted">{gpuResult.rack_plan.pdu_tier_label}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Power/Rack</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.rack_plan.power_per_rack_kw} kW</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Total Power (PUE)</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.rack_plan.pue_adjusted_power_kw} kW</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">U Utilization</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.rack_plan.u_utilization_pct}%</span>
                  </div>
                  {/* Headroom bars */}
                  <div className="space-y-2 pt-2">
                    <div>
                      <div className="flex items-center justify-between text-[10px] mb-1">
                        <span className="text-gray-500">PDU Headroom</span>
                        <span className="font-mono text-gray-400">{gpuResult.rack_plan.pdu_headroom_pct}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={cn("h-full rounded-full", gpuResult.rack_plan.pdu_headroom_pct > 20 ? "bg-emerald-500" : gpuResult.rack_plan.pdu_headroom_pct > 10 ? "bg-amber-500" : "bg-red-500")}
                          style={{ width: `${Math.min(100, 100 - gpuResult.rack_plan.pdu_headroom_pct)}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between text-[10px] mb-1">
                        <span className="text-gray-500">Cooling Headroom</span>
                        <span className="font-mono text-gray-400">{gpuResult.rack_plan.cooling_headroom_pct}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className={cn("h-full rounded-full", gpuResult.rack_plan.cooling_headroom_pct > 20 ? "bg-blue-500" : gpuResult.rack_plan.cooling_headroom_pct > 10 ? "bg-amber-500" : "bg-red-500")}
                          style={{ width: `${Math.min(100, 100 - gpuResult.rack_plan.cooling_headroom_pct)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  {gpuResult.rack_plan.density_warning && (
                    <div className="flex items-center gap-2 rounded-md bg-amber-50 border border-amber-200 p-2 text-[10px] text-amber-700">
                      <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                      {gpuResult.rack_plan.density_warning}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Cost breakdown */}
          {gpuResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-3.5 w-3.5 text-gray-400" /> Cost Breakdown (36m)
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Total TCO</span>
                    <span className="font-mono text-sm font-bold text-gray-900">{formatCurrency(gpuResult.tco_gbp)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">CapEx</span>
                    <span className="font-mono text-sm text-blue-600">{formatCurrency(gpuResult.capex_gbp)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">OpEx/month</span>
                    <span className="font-mono text-sm text-emerald-600">{formatCurrency(gpuResult.opex_monthly_gbp)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Tokens/£/month</span>
                    <span className="font-mono text-sm text-gray-700">{formatNumber(gpuResult.tokens_per_gbp)}</span>
                  </div>

                  {/* Stacked bar */}
                  {costData.length > 0 && (
                    <div className="pt-2">
                      <div className="flex h-4 w-full overflow-hidden rounded-full bg-gray-100">
                        {costData.map((d) => {
                          const total = costData.reduce((s, c) => s + c.value, 0);
                          const pct = total > 0 ? (d.value / total) * 100 : 0;
                          return (
                            <div
                              key={d.name}
                              className="h-full transition-all"
                              style={{ width: `${pct}%`, backgroundColor: d.fill }}
                              title={`${d.name}: ${formatCurrency(d.value)} (${pct.toFixed(0)}%)`}
                            />
                          );
                        })}
                      </div>
                      <div className="mt-2 flex items-center gap-4 text-[10px] text-gray-500">
                        {costData.map((d) => (
                          <span key={d.name} className="flex items-center gap-1">
                            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: d.fill }} />
                            {d.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Performance metrics */}
          {gpuResult && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-3.5 w-3.5 text-gray-400" /> Performance
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Decode</span>
                    <span className="font-mono text-sm font-bold text-gray-900">{formatNumber(gpuResult.decode_tokens_per_sec)} tok/s</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Prefill</span>
                    <span className="font-mono text-sm text-gray-700">{formatNumber(gpuResult.prefill_tokens_per_sec)} tok/s</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">KV Cache</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.kv_cache_gb?.toFixed(2) ?? "—"} GB</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Max Context</span>
                    <span className="font-mono text-sm text-gray-700">{gpuResult.max_context_length ? formatNumber(gpuResult.max_context_length) : "—"} tokens</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Composite Score</span>
                    <span className="font-mono text-sm font-bold" style={{ color }}>{gpuResult.composite_score?.toFixed(3)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Warnings */}
          {gpuResult && gpuResult.warnings.length > 0 && (
            <Card className="border-amber-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-amber-600">
                  <AlertTriangle className="h-3.5 w-3.5" /> Warnings
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <ul className="space-y-2">
                  {gpuResult.warnings.map((w, i) => (
                    <li key={i} className="text-xs text-amber-700 flex items-start gap-2">
                      <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                      {w}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Verdict */}
          {gpu.verdict && (
            <Card>
              <CardHeader>
                <CardTitle>Verdict</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-xs leading-relaxed text-gray-600">{gpu.verdict}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <Card className="p-3">
      <div className="flex items-center gap-1.5 text-gray-400 mb-1">
        {icon}
        <span className="text-[9px] font-semibold uppercase tracking-widest">{label}</span>
      </div>
      <div className="font-mono text-sm font-bold text-gray-900">{value}</div>
      {sub && <div className="text-[9px] text-gray-400">{sub}</div>}
    </Card>
  );
}

function normalize(
  val: number | null | undefined,
  vals: number[],
  invert = false
): number {
  const v = val ?? 0;
  const mn = Math.min(...vals);
  const mx = Math.max(...vals);
  if (mx === mn) return 80;
  const n = ((v - mn) / (mx - mn)) * 100;
  return invert ? 100 - n : n;
}
