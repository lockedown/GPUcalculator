"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { GPU } from "@/types";
import { GPU_COLORS } from "@/types";
import { formatNumber } from "@/lib/utils";
import { Droplets, Wind, ChevronRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function HardwarePage() {
  const [gpus, setGpus] = useState<GPU[]>([]);
  const [vendorFilter, setVendorFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.hardware.list(vendorFilter ?? undefined).then((data) => {
      setGpus(data);
      setLoading(false);
    });
  }, [vendorFilter]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-gray-900">Hardware Catalog</h1>
        <p className="mt-1 text-sm text-gray-500">
          All GPU specifications from the Finance GPU Benchmark Matrix — 9 GPUs across NVIDIA and AMD.
        </p>
      </div>

      {/* Vendor filter */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">Vendor:</span>
        {[null, "NVIDIA", "AMD"].map((v) => (
          <Button
            key={v ?? "all"}
            variant={vendorFilter === v ? "default" : "outline"}
            size="sm"
            onClick={() => setVendorFilter(v)}
            className="text-[10px] uppercase tracking-wide h-7"
          >
            {v ?? "All"}
          </Button>
        ))}
      </div>

      {/* GPU Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="p-5">
                <Skeleton className="h-6 w-32 mb-2" />
                <Skeleton className="h-3 w-48 mb-4" />
                <div className="grid grid-cols-2 gap-3">
                  {Array.from({ length: 8 }).map((_, j) => (
                    <Skeleton key={j} className="h-8 w-full" />
                  ))}
                </div>
              </Card>
            ))
          : gpus.map((gpu) => (
              <Card
                key={gpu.id}
                className="relative overflow-hidden p-5 transition-shadow hover:shadow-md group"
              >
                {/* Color accent bar */}
                <div
                  className="absolute left-0 top-0 h-1 w-full"
                  style={{ backgroundColor: GPU_COLORS[gpu.name] || "#6b7280" }}
                />

                <div className="flex items-start justify-between">
                  <div>
                    <h3
                      className="text-lg font-bold tracking-tight"
                      style={{ color: GPU_COLORS[gpu.name] || "#111" }}
                    >
                      {gpu.name}
                    </h3>
                    <p className="text-[11px] text-gray-400">
                      {gpu.vendor} · {gpu.generation} · {gpu.form_factor}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {gpu.cooling_type === "liquid" ? (
                      <Droplets className="h-4 w-4 text-blue-400" />
                    ) : (
                      <Wind className="h-4 w-4 text-gray-300" />
                    )}
                    {gpu.is_estimated && <Badge variant="warning">EST</Badge>}
                  </div>
                </div>

                {/* Specs grid */}
                <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2">
                  <Stat label="HBM" value={`${gpu.hbm_capacity_gb}GB`} sub={gpu.hbm_type || ""} />
                  <Stat label="Mem BW" value={`${gpu.mem_bandwidth_tb_s} TB/s`} />
                  <Stat label="BF16" value={gpu.bf16_tflops ? `${formatNumber(gpu.bf16_tflops)} TFLOPS` : "—"} />
                  <Stat label="FP64" value={gpu.fp64_tflops ? `${gpu.fp64_tflops} TFLOPS` : "—"} />
                  <Stat label="FP8" value={gpu.fp8_tflops ? `${formatNumber(gpu.fp8_tflops)} TFLOPS` : "N/A"} />
                  <Stat label="TDP" value={gpu.tdp_watts ? `${gpu.tdp_watts}W` : "—"} />
                  <Stat label="Interconnect" value={gpu.intra_node_interconnect || "—"} />
                  <Stat
                    label="Fabric BW"
                    value={
                      gpu.is_rack_scale && gpu.rack_fabric_bw_tb_s
                        ? `${gpu.rack_fabric_bw_tb_s} TB/s`
                        : gpu.interconnect_bw_gb_s
                        ? `${gpu.interconnect_bw_gb_s} GB/s`
                        : "—"
                    }
                  />
                </div>

                {/* Pricing & availability */}
                <div className="mt-3 flex items-center justify-between gap-3 border-t border-gray-100 pt-3">
                  <div className="flex items-center gap-3">
                    {gpu.msrp_usd && (
                      <span className="font-mono text-[11px] text-gray-600">
                        ~${gpu.msrp_usd.toLocaleString()}/GPU
                      </span>
                    )}
                    {gpu.release_date && (
                      <span className="text-[10px] text-gray-400">{gpu.release_date}</span>
                    )}
                  </div>
                  <Link
                    href={`/gpu/${gpu.id}`}
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-blue-600"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Link>
                </div>

                {/* Verdict */}
                {gpu.verdict && (
                  <div className="mt-3 border-t border-gray-100 pt-3">
                    <p className="text-[11px] leading-relaxed text-gray-500">
                      {gpu.verdict.split("|")[0].trim().slice(0, 200)}
                      {gpu.verdict.length > 200 ? "…" : ""}
                    </p>
                  </div>
                )}
              </Card>
            ))}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-[9px] font-semibold uppercase tracking-widest text-gray-400">{label}</div>
      <div className="font-mono text-[11px] font-medium text-gray-800">{value}</div>
      {sub && <div className="text-[9px] text-gray-400">{sub}</div>}
    </div>
  );
}
