/**
 * CSV export for the per-GPU comparison results table. Defines the column
 * spec once (header + value extractor) so adding/removing columns doesn't
 * require keeping two parallel lists in sync.
 */

import type { GPUResult } from "@/types";

interface Column {
  header: string;
  /** Extracts the cell value for a given result + zero-based row index. */
  value: (r: GPUResult, i: number) => string | number | null | undefined;
}

const COLUMNS: Column[] = [
  { header: "Rank", value: (_r, i) => i + 1 },
  { header: "GPU", value: (r) => r.gpu_name },
  { header: "Vendor", value: (r) => r.gpu_vendor },
  { header: "Score", value: (r) => r.composite_score?.toFixed(4) ?? "" },
  { header: "Decode tok/s", value: (r) => r.decode_tokens_per_sec?.toFixed(0) ?? "" },
  { header: "Prefill tok/s", value: (r) => r.prefill_tokens_per_sec?.toFixed(0) ?? "" },
  { header: "TTFT (ms)", value: (r) => r.ttft_ms?.toFixed(0) ?? "" },
  { header: "TPOT (ms)", value: (r) => r.tpot_ms?.toFixed(1) ?? "" },
  { header: "Per-user decode tok/s", value: (r) => r.per_user_decode_tps?.toFixed(1) ?? "" },
  { header: "Tenancy", value: (r) => r.tenancy_mode_applied ?? "dedicated" },
  { header: "Tenants/GPU", value: (r) => r.tenants_per_gpu ?? "" },
  { header: "Per-tenant decode tok/s", value: (r) => r.per_tenant_decode_tps?.toFixed(1) ?? "" },
  {
    header: "MoE Active%",
    value: (r) => (r.moe_active_param_fraction != null ? (r.moe_active_param_fraction * 100).toFixed(0) : ""),
  },
  { header: "MoE BW/token (GB)", value: (r) => r.moe_effective_bw_per_token_gb?.toFixed(1) ?? "" },
  { header: "MoE Routing overhead%", value: (r) => r.moe_routing_overhead_pct?.toFixed(0) ?? "" },
  { header: "TCO (USD)", value: (r) => r.tco_usd?.toFixed(0) ?? "" },
  { header: "CapEx (USD)", value: (r) => r.capex_usd?.toFixed(0) ?? "" },
  { header: "OpEx/mo (USD)", value: (r) => r.opex_monthly_usd?.toFixed(0) ?? "" },
  { header: "Carbon kg/yr", value: (r) => r.carbon_kg_per_year?.toFixed(0) ?? "" },
  { header: "Tokens/USD/mo", value: (r) => r.tokens_per_usd?.toFixed(0) ?? "" },
  { header: "Complexity", value: (r) => r.complexity_score?.toFixed(2) ?? "" },
  { header: "Availability", value: (r) => r.availability_score?.toFixed(2) ?? "" },
  { header: "GPU Count", value: (r) => r.topology?.gpu_count ?? "" },
  { header: "Nodes", value: (r) => r.topology?.nodes ?? "" },
  { header: "Strategy", value: (r) => r.topology?.parallelism_strategy ?? "" },
  { header: "Serving Mode", value: (r) => r.topology?.serving_mode ?? "colocated" },
  { header: "Prefill GPUs", value: (r) => r.topology?.prefill_gpu_count ?? "" },
  { header: "Decode GPUs", value: (r) => r.topology?.decode_gpu_count ?? "" },
  { header: "Racks", value: (r) => r.rack_plan?.total_racks ?? "" },
  { header: "Power/Rack (kW)", value: (r) => r.rack_plan?.power_per_rack_kw ?? "" },
  { header: "PDU Tier", value: (r) => r.rack_plan?.pdu_tier_label ?? "" },
  { header: "Warnings", value: (r) => r.warnings.join("; ") },
];

function escapeCell(cell: unknown): string {
  return `"${String(cell ?? "").replace(/"/g, '""')}"`;
}

/** Build the full CSV text for a list of comparison results. */
export function buildComparisonCsv(results: GPUResult[]): string {
  const headerRow = COLUMNS.map((c) => escapeCell(c.header)).join(",");
  const dataRows = results.map((r, i) =>
    COLUMNS.map((c) => escapeCell(c.value(r, i))).join(","),
  );
  return [headerRow, ...dataRows].join("\n");
}

/** Trigger a browser download of the comparison results as a CSV file. */
export function downloadComparisonCsv(results: GPUResult[]): void {
  const csv = buildComparisonCsv(results);
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `gpu_comparison_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
