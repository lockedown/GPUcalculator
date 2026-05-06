/**
 * GPU catalogue types — the hardware inventory and its supporting metadata
 * (benchmarks, availability, networking options, price history).
 */

import type { NVLinkTopology } from "./enums";

export interface GPU {
  id: number;
  name: string;
  vendor: string;
  generation: string;
  form_factor: string;
  hbm_capacity_gb: number;
  hbm_type: string | null;
  mem_bandwidth_tb_s: number;
  bf16_tflops: number | null;
  fp64_tflops: number | null;
  fp8_tflops: number | null;
  fp4_tflops: number | null;
  tdp_watts: number | null;
  cooling_type: string;
  intra_node_interconnect: string | null;
  interconnect_bw_gb_s: number | null;
  // Intra-node fabric topology — drives bandwidth-derate decisions.
  // Values: 'nvswitch' | 'nvl_fabric' | 'point_to_point' | 'none' | null.
  nvlink_topology: NVLinkTopology | null;
  max_gpus_per_node: number;
  is_rack_scale: boolean;
  rack_gpu_count: number | null;
  rack_fabric_bw_tb_s: number | null;
  msrp_usd: number | null;
  // ISO YYYY-MM-DD when ``msrp_usd`` was last verified against a known-good
  // source (NVIDIA / AMD official MSRPs, UBS / SemiAnalysis channel surveys).
  // null on legacy rows that pre-date the freshness-stamp rollout.
  msrp_as_of: string | null;
  is_estimated: boolean;
  release_date: string | null;
  verdict: string | null;
}

export interface GPUDetail extends GPU {
  benchmarks: BenchmarkScore[];
  availability: AvailabilityInfo | null;
}

export interface BenchmarkScore {
  id: number;
  gpu_id: number;
  benchmark_name: string;
  workload_category: string;
  workload_description: string | null;
  rating: string | null;
  bar_pct: number | null;
  metric_value: string | null;
  metric_numeric: number | null;
  metric_unit: string | null;
}

export interface BenchmarkWithGPU extends BenchmarkScore {
  gpu_name: string | null;
  gpu_vendor: string | null;
}

export interface AvailabilityInfo {
  id: number;
  gpu_id: number;
  lead_time_weeks: number;
  supply_status: string;
}

export interface NetworkingOption {
  id: number;
  name: string;
  type: string;
  vendor: string;
  generation: string | null;
  bandwidth_gb_s: number;
  latency_us: number | null;
  is_inter_node: number;
  notes: string | null;
}

export interface PriceHistoryEntry {
  id: number;
  gpu_id: number;
  date: string;
  price_usd: number;
  source: string;
}

export interface PriceHistoryByGPU {
  gpu_id: number;
  gpu_name: string;
  prices: PriceHistoryEntry[];
}
