"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { PriceHistoryByGPU } from "@/types";
import { GPU_COLORS } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export default function PricesPage() {
  const [data, setData] = useState<PriceHistoryByGPU[]>([]);
  const [loading, setLoading] = useState(true);
  const [excludeRackScale, setExcludeRackScale] = useState(true);

  useEffect(() => {
    api.prices.list().then((d) => {
      setData(d);
      setLoading(false);
    });
  }, []);

  // Rack-scale GPUs (NVL72) have wildly different price ranges
  const rackScaleNames = ["GB200 NVL72", "GB300 NVL72"];
  const filtered = excludeRackScale
    ? data.filter((d) => !rackScaleNames.includes(d.gpu_name))
    : data;

  // Build unified timeline data for Recharts
  const allDates = new Set<string>();
  for (const gpu of filtered) {
    for (const p of gpu.prices) {
      allDates.add(p.date);
    }
  }
  const sortedDates = Array.from(allDates).sort();

  const chartData = sortedDates.map((date) => {
    const point: Record<string, string | number> = { date };
    for (const gpu of filtered) {
      const price = gpu.prices.find((p) => p.date === date);
      if (price) {
        point[gpu.gpu_name] = price.price_usd;
      }
    }
    return point;
  });

  // Latest prices for summary cards
  const latestPrices = filtered.map((gpu) => {
    const latest = gpu.prices[gpu.prices.length - 1];
    const first = gpu.prices[0];
    const change = first && latest ? ((latest.price_usd - first.price_usd) / first.price_usd) * 100 : 0;
    return {
      gpu_name: gpu.gpu_name,
      price: latest?.price_usd ?? 0,
      source: latest?.source ?? "unknown",
      change,
      dataPoints: gpu.prices.length,
    };
  });

  if (loading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-16 w-full" />
            </Card>
          ))}
        </div>
        <Card className="p-5">
          <Skeleton className="h-80 w-full" />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">GPU Price Tracking</h1>
        <p className="mt-1 text-sm text-gray-500">
          Historical pricing trends for datacenter GPUs — MSRP, market, and estimated prices.
        </p>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <Button
          variant={excludeRackScale ? "default" : "outline"}
          size="sm"
          onClick={() => setExcludeRackScale(true)}
          className="text-[10px] uppercase tracking-wide h-7"
        >
          Per-GPU Pricing
        </Button>
        <Button
          variant={!excludeRackScale ? "default" : "outline"}
          size="sm"
          onClick={() => setExcludeRackScale(false)}
          className="text-[10px] uppercase tracking-wide h-7"
        >
          Include Rack-Scale
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {latestPrices
          .sort((a, b) => a.price - b.price)
          .map((p) => (
            <Card key={p.gpu_name} className="p-3 relative overflow-hidden">
              <div
                className="absolute left-0 top-0 h-1 w-full"
                style={{ backgroundColor: GPU_COLORS[p.gpu_name] || "#6b7280" }}
              />
              <div className="text-xs font-bold" style={{ color: GPU_COLORS[p.gpu_name] || "#111" }}>
                {p.gpu_name}
              </div>
              <div className="font-mono text-lg font-bold text-gray-900 mt-1">
                ${p.price.toLocaleString()}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <Badge
                  variant={p.source === "market" ? "success" : p.source === "msrp" ? "muted" : "warning"}
                  className="text-[8px]"
                >
                  {p.source}
                </Badge>
                {p.change !== 0 && (
                  <span
                    className={cn(
                      "text-[10px] font-mono font-medium",
                      p.change < 0 ? "text-emerald-600" : "text-red-500"
                    )}
                  >
                    {p.change > 0 ? "+" : ""}{p.change.toFixed(1)}%
                  </span>
                )}
              </div>
            </Card>
          ))}
      </div>

      {/* Price chart */}
      <Card>
        <CardHeader>
          <CardTitle>Price History (USD per GPU)</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={chartData} margin={{ left: 20, right: 20, top: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#6b7280" }}
                  tickFormatter={(d: string) => {
                    const [y, m] = d.split("-");
                    return `${m}/${y.slice(2)}`;
                  }}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#6b7280" }}
                  tickFormatter={(v: number) =>
                    v >= 1000000 ? `$${(v / 1000000).toFixed(1)}M` : `$${(v / 1000).toFixed(0)}K`
                  }
                />
                <Tooltip
                  contentStyle={{ fontSize: "11px", borderRadius: "8px", border: "1px solid #e5e7eb" }}
                  formatter={(value) => [`$${Number(value).toLocaleString()}`, ""]}
                  labelFormatter={(label) => {
                    const [y, m] = String(label).split("-");
                    const months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
                    return `${months[parseInt(m)]} ${y}`;
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: "10px", fontFamily: "monospace" }}
                  iconSize={8}
                />
                {filtered.map((gpu) => (
                  <Line
                    key={gpu.gpu_name}
                    type="monotone"
                    dataKey={gpu.gpu_name}
                    stroke={GPU_COLORS[gpu.gpu_name] || "#6b7280"}
                    strokeWidth={2}
                    dot={{ r: 3, fill: GPU_COLORS[gpu.gpu_name] || "#6b7280" }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 py-8 text-center">No price data available. Re-seed the database.</p>
          )}
        </CardContent>
      </Card>

      {/* Rack-scale pricing (separate) */}
      {excludeRackScale && data.some((d) => rackScaleNames.includes(d.gpu_name)) && (
        <Card>
          <CardHeader>
            <CardTitle>Rack-Scale Pricing (Full System)</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid gap-4 sm:grid-cols-2">
              {data
                .filter((d) => rackScaleNames.includes(d.gpu_name))
                .map((gpu) => {
                  const latest = gpu.prices[gpu.prices.length - 1];
                  return (
                    <div key={gpu.gpu_name} className="rounded-lg border border-gray-100 p-4">
                      <div className="text-sm font-bold" style={{ color: GPU_COLORS[gpu.gpu_name] }}>
                        {gpu.gpu_name}
                      </div>
                      <div className="font-mono text-2xl font-bold text-gray-900 mt-1">
                        ${latest?.price_usd.toLocaleString()}
                      </div>
                      <div className="text-[10px] text-gray-400 mt-1">
                        72 GPUs per system · {gpu.prices.length} data points
                      </div>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
