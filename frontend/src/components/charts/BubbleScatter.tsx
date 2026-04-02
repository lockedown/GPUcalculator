"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { GPUResult } from "@/types";
import { GPU_COLORS } from "@/types";
import { formatNumber, formatCurrency } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface Props {
  results: GPUResult[];
  width?: number;
  height?: number;
}

export default function BubbleScatter({ results, width = 800, height = 480 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || results.length === 0) return;

    const margin = { top: 30, right: 30, bottom: 50, left: 70 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Filter out rack-scale for readability unless only rack-scale exists
    const data = results.filter((r) => r.tco_gbp != null && r.tokens_per_sec != null);
    if (data.length === 0) return;

    // Scales
    const xExtent = d3.extent(data, (d) => d.tco_gbp!) as [number, number];
    const yExtent = d3.extent(data, (d) => d.tokens_per_sec!) as [number, number];

    const x = d3.scaleLog().domain([Math.max(1, xExtent[0] * 0.8), xExtent[1] * 1.2]).range([0, w]).nice();
    const y = d3.scaleLog().domain([Math.max(1, yExtent[0] * 0.8), yExtent[1] * 1.2]).range([h, 0]).nice();

    // Bubble size = availability (larger = faster delivery)
    const sizeScale = d3
      .scaleSqrt()
      .domain([0, 1])
      .range([6, 28]);

    // Color = complexity (green = easy, red = hard)
    const colorScale = d3
      .scaleLinear<string>()
      .domain([0, 5, 10])
      .range(["#ef4444", "#f59e0b", "#22c55e"]);

    // Grid lines
    g.append("g")
      .attr("class", "grid")
      .attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).ticks(6).tickSize(-h).tickFormat(() => ""))
      .selectAll("line")
      .attr("stroke", "#f0f0f0");

    g.append("g")
      .attr("class", "grid")
      .call(d3.axisLeft(y).ticks(6).tickSize(-w).tickFormat(() => ""))
      .selectAll("line")
      .attr("stroke", "#f0f0f0");

    // Axes
    g.append("g")
      .attr("transform", `translate(0,${h})`)
      .call(d3.axisBottom(x).ticks(6, "~s"))
      .selectAll("text")
      .attr("font-size", "10px")
      .attr("fill", "#6b7280");

    g.append("g")
      .call(d3.axisLeft(y).ticks(6, "~s"))
      .selectAll("text")
      .attr("font-size", "10px")
      .attr("fill", "#6b7280");

    // Axis labels
    g.append("text")
      .attr("x", w / 2)
      .attr("y", h + 40)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#9ca3af")
      .attr("font-family", "monospace")
      .text("Total Cost of Ownership (£)");

    g.append("text")
      .attr("x", -h / 2)
      .attr("y", -55)
      .attr("transform", "rotate(-90)")
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#9ca3af")
      .attr("font-family", "monospace")
      .text("Tokens/sec (decode)");

    // Tooltip
    const tooltip = d3
      .select("body")
      .append("div")
      .attr("class", "gpu-tooltip")
      .style("position", "absolute")
      .style("background", "white")
      .style("border", "1px solid #e5e7eb")
      .style("border-radius", "8px")
      .style("padding", "10px 14px")
      .style("font-size", "11px")
      .style("box-shadow", "0 4px 12px rgba(0,0,0,0.1)")
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("z-index", "1000");

    // Bubbles
    const bubbles = g
      .selectAll("circle")
      .data(data)
      .join("circle")
      .attr("cx", (d) => x(d.tco_gbp!))
      .attr("cy", (d) => y(d.tokens_per_sec!))
      .attr("r", 0)
      .attr("fill", (d) => GPU_COLORS[d.gpu_name] || colorScale(d.complexity_score ?? 5))
      .attr("fill-opacity", 0.75)
      .attr("stroke", (d) => GPU_COLORS[d.gpu_name] || colorScale(d.complexity_score ?? 5))
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.9)
      .style("cursor", "pointer");

    bubbles
      .transition()
      .duration(800)
      .ease(d3.easeCubicOut)
      .attr("r", (d) => sizeScale(d.availability_score ?? 0.3));

    bubbles
      .on("mouseover", function (event, d) {
        d3.select(this).attr("fill-opacity", 1).attr("stroke-width", 3);
        tooltip
          .style("opacity", 1)
          .html(
            `<div style="font-weight:600;margin-bottom:4px;color:${GPU_COLORS[d.gpu_name] || "#333"}">${d.gpu_name}</div>
             <div style="color:#6b7280">TCO: ${formatCurrency(d.tco_gbp)}</div>
             <div style="color:#6b7280">Decode: ${formatNumber(d.tokens_per_sec)} tok/s</div>
             <div style="color:#6b7280">Complexity: ${d.complexity_score?.toFixed(1)}/10</div>
             <div style="color:#6b7280">Availability: ${((d.availability_score ?? 0) * 100).toFixed(0)}%</div>
             ${d.topology ? `<div style="color:#6b7280">GPUs: ${d.topology.gpu_count} (${d.topology.parallelism_strategy})</div>` : ""}
             ${d.warnings.length ? `<div style="color:#f59e0b;margin-top:4px;font-size:10px">${d.warnings[0]}</div>` : ""}`
          );
      })
      .on("mousemove", function (event) {
        tooltip
          .style("left", event.pageX + 14 + "px")
          .style("top", event.pageY - 14 + "px");
      })
      .on("mouseout", function () {
        d3.select(this).attr("fill-opacity", 0.75).attr("stroke-width", 2);
        tooltip.style("opacity", 0);
      });

    // Labels
    g.selectAll(".label")
      .data(data)
      .join("text")
      .attr("class", "label")
      .attr("x", (d) => x(d.tco_gbp!))
      .attr("y", (d) => y(d.tokens_per_sec!) - sizeScale(d.availability_score ?? 0.3) - 5)
      .attr("text-anchor", "middle")
      .attr("font-size", "9px")
      .attr("font-family", "monospace")
      .attr("fill", (d) => GPU_COLORS[d.gpu_name] || "#6b7280")
      .attr("font-weight", "600")
      .text((d) => d.gpu_name);

    return () => {
      tooltip.remove();
    };
  }, [results, width, height]);

  return (
    <Card className="overflow-x-auto">
      <CardHeader className="flex-row items-center justify-between gap-4 pb-2">
        <CardTitle>Sweet Spot — Cost vs Performance</CardTitle>
        <div className="flex items-center gap-4 text-[10px] text-gray-400 flex-shrink-0">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-green-500" /> Easy
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" /> Moderate
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-red-500" /> Complex
          </span>
          <span className="text-gray-300">|</span>
          <span>Bubble size = availability</span>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <svg ref={svgRef} width={width} height={height} className="mx-auto" />
      </CardContent>
    </Card>
  );
}
