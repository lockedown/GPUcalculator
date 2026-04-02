"use client";

import {
  Radar,
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { GPUResult } from "@/types";
import { GPU_COLORS } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface Props {
  results: GPUResult[];
  maxItems?: number;
}

export default function RadarChart({ results, maxItems = 5 }: Props) {
  const top = results.slice(0, maxItems);

  if (top.length === 0) {
    return (
      <Card>
        <CardContent className="flex h-64 items-center justify-center text-sm text-gray-400">
          Run a comparison to see the radar chart
        </CardContent>
      </Card>
    );
  }

  // Normalize each metric to 0-100
  const allTps = top.map((r) => r.tokens_per_sec ?? 0);
  const allTco = top.map((r) => r.tco_gbp ?? 0);
  const allCx = top.map((r) => r.complexity_score ?? 0);
  const allAv = top.map((r) => r.availability_score ?? 0);

  const norm = (val: number, vals: number[], invert = false) => {
    const mn = Math.min(...vals);
    const mx = Math.max(...vals);
    if (mx === mn) return 80;
    const n = ((val - mn) / (mx - mn)) * 100;
    return invert ? 100 - n : n;
  };

  const data = [
    {
      metric: "Performance",
      ...Object.fromEntries(top.map((r) => [r.gpu_name, norm(r.tokens_per_sec ?? 0, allTps)])),
    },
    {
      metric: "Cost Efficiency",
      ...Object.fromEntries(top.map((r) => [r.gpu_name, norm(r.tco_gbp ?? 0, allTco, true)])),
    },
    {
      metric: "Simplicity",
      ...Object.fromEntries(top.map((r) => [r.gpu_name, norm(r.complexity_score ?? 0, allCx)])),
    },
    {
      metric: "Availability",
      ...Object.fromEntries(top.map((r) => [r.gpu_name, norm(r.availability_score ?? 0, allAv)])),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Multi-Metric Radar</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <ResponsiveContainer width="100%" height={320}>
          <RechartsRadar data={data} cx="50%" cy="50%" outerRadius="75%">
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fontSize: 10, fill: "#6b7280", fontFamily: "monospace" }}
            />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
            {top.map((r) => (
              <Radar
                key={r.gpu_name}
                name={r.gpu_name}
                dataKey={r.gpu_name}
                stroke={GPU_COLORS[r.gpu_name] || "#6b7280"}
                fill={GPU_COLORS[r.gpu_name] || "#6b7280"}
                fillOpacity={0.12}
                strokeWidth={2}
              />
            ))}
            <Legend
              wrapperStyle={{ fontSize: "10px", fontFamily: "monospace" }}
              iconSize={8}
            />
            <Tooltip
              contentStyle={{ fontSize: "11px", borderRadius: "8px", border: "1px solid #e5e7eb" }}
              formatter={(value) => `${Number(value).toFixed(0)}`}
            />
          </RechartsRadar>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
