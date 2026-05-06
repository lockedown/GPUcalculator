"use client";

import type { GPUResult } from "@/types";
import { GPU_COLORS } from "@/types";
import { useStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { formatCurrency, formatNumber } from "@/lib/utils";
import {
  Network,
  Server,
  Banknote,
  Zap,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Gauge,
  Users,
  Boxes,
} from "lucide-react";

interface Props {
  result: GPUResult | null;
  /** Top-N reasons explaining why this GPU was chosen as the sweet spot. */
  reasons?: string[];
  loading?: boolean;
}

// Badge styling for the optimizer's structured violation codes.
const CODE_LABELS: Record<string, { label: string; tone: "warn" | "info" }> = {
  PRE_GA: { label: "Pre-GA specs", tone: "info" },
  MARGINAL_AIR_COOLING: { label: "Marginal air cooling", tone: "warn" },
  COOLING_SOFT: { label: "Liquid recommended", tone: "warn" },
  TPOT_MISSED: { label: "TPOT target missed", tone: "warn" },
  MIG_NVLINK_DISABLED: { label: "NVLink disabled (MIG)", tone: "info" },
  RUNAI_TIME_SLICED: { label: "Time-sliced (Run:ai)", tone: "info" },
  DISAGG_RECOMMENDED: { label: "Disaggregation recommended", tone: "info" },
};

export default function SweetSpotDetail({ result, reasons, loading }: Props) {
  const amortMonths = useStore((s) => s.constraints.amortization_months);
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sweet Spot Detail</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!result) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sweet Spot Detail</CardTitle>
        </CardHeader>
        <CardContent className="flex h-64 items-center justify-center text-sm text-gray-400">
          Adjust the workload above to see a recommendation.
        </CardContent>
      </Card>
    );
  }

  const t = result.topology;
  const r = result.rack_plan;
  const totalGpus = t?.gpu_count ?? 0;
  const monthlyOpex = result.opex_monthly_usd ?? 0;
  const monthlyAmortised = (result.tco_usd ?? 0) / amortMonths;
  const monthlyCapexShare = Math.max(0, monthlyAmortised - monthlyOpex);

  const advisoryCodes = result.violation_codes.filter((c) => c in CODE_LABELS);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sweet Spot Detail</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Headline */}
        <div className="flex items-baseline justify-between gap-2 border-b border-gray-100 pb-3">
          <div>
            <div
              className="text-lg font-bold leading-tight"
              style={{ color: GPU_COLORS[result.gpu_name] || "#111" }}
            >
              {result.gpu_name}
            </div>
            <div className="mt-0.5 text-[11px] text-gray-500">
              {result.gpu_vendor} · score {result.composite_score?.toFixed(3)}
            </div>
          </div>
          <Badge variant="success" className="rounded-full text-[10px]">
            <CheckCircle2 className="mr-1 h-3 w-3" /> Recommended
          </Badge>
        </div>

        {/* Why — top-N reasons explaining this pick */}
        {reasons && reasons.length > 0 && (
          <div className="rounded-md border border-emerald-100 bg-emerald-50/40 px-3 py-2">
            <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-emerald-700">
              <CheckCircle2 className="h-3 w-3" /> Why this GPU
            </div>
            <ul className="space-y-0.5">
              {reasons.map((reason, i) => (
                <li key={i} className="text-[11px] leading-snug text-emerald-900">
                  · {reason}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Topology */}
        <Section
          icon={<Network className="h-3.5 w-3.5" />}
          title="Topology"
          tooltip="GPUs sized to fit model + per-replica KV cache, with DP replicas added for throughput. TP rounded up to a power of 2 (NCCL efficiency)."
          learnMore="topology"
        >
          <Row label="GPUs required" value={`${totalGpus}×`} />
          <Row label="Strategy" value={t?.parallelism_strategy ?? "—"} />
          <Row
            label="TP / PP / DP"
            value={t ? `${t.tp_degree} / ${t.pp_degree} / ${t.dp_degree}` : "—"}
          />
          {t && t.nodes > 1 && (
            <Row label="Nodes" value={`${t.nodes} × ${t.gpus_per_node}-GPU`} />
          )}
          {t && t.cross_node_latency_penalty > 0 && (
            <Row
              label="Cross-node penalty"
              value={`-${(t.cross_node_latency_penalty * 100).toFixed(0)}%`}
              valueClass="text-amber-600"
            />
          )}
          {t && t.serving_mode === "disaggregated" && (
            <>
              <Row
                label="↳ Prefill pool"
                value={`${t.prefill_gpu_count}× GPU`}
                valueClass="text-blue-700"
              />
              <Row
                label="↳ Decode pool"
                value={`${t.decode_gpu_count}× GPU`}
                valueClass="text-emerald-700"
              />
            </>
          )}
        </Section>

        {/* Rack plan */}
        {r && (
          <Section
            icon={<Server className="h-3.5 w-3.5" />}
            title="Rack plan"
            tooltip="42U rack layout with PDU tier picked from cooling type + per-GPU TDP. Cooling envelope is matched to the PDU tier (25/40/120/132 kW)."
            learnMore="constraints"
          >
            <Row
              label="Racks"
              value={`${r.total_racks} × ${r.gpus_per_rack}-GPU`}
            />
            <Row label="PDU tier" value={r.pdu_tier_label} />
            <Row
              label="Power / rack"
              value={`${r.power_per_rack_kw.toFixed(1)} kW`}
            />
            <Row
              label="Cooling envelope"
              value={`${r.cooling_capacity_kw.toFixed(0)} kW (${r.cooling_headroom_pct.toFixed(0)}% headroom)`}
              valueClass={r.fits_cooling ? "" : "text-rose-600 font-semibold"}
            />
            <Row
              label="Total facility power"
              value={`${r.pue_adjusted_power_kw.toFixed(1)} kW (PUE-adjusted)`}
            />
          </Section>
        )}

        {/* MoE detail (only when workload.is_moe) */}
        {result.moe_active_param_fraction != null && (
          <Section
            icon={<Boxes className="h-3.5 w-3.5" />}
            title="MoE detail"
            tooltip={
              <>
                <strong>Active fraction</strong> = active_experts ÷ num_experts. The bandwidth-bound denominator on decode is just the active-expert weight bytes per token. <strong>Routing overhead</strong> is the all-to-all dispatch+combine penalty applied to decode tps: 0% on a single GPU, ~12% intra-node, ~22% multi-node. The decode_tokens_per_sec figure already has this baked in.
              </>
            }
          >
            <Row
              label="Active params / token"
              value={`${(result.moe_active_param_fraction * 100).toFixed(0)}%`}
            />
            {result.moe_effective_bw_per_token_gb != null && (
              <Row
                label="Active weight bytes / token"
                value={`${result.moe_effective_bw_per_token_gb.toFixed(1)} GB`}
              />
            )}
            {result.moe_routing_overhead_pct != null && (
              <Row
                label="All-to-all routing overhead"
                value={
                  result.moe_routing_overhead_pct > 0
                    ? `−${result.moe_routing_overhead_pct.toFixed(0)}%`
                    : "0% (single-GPU)"
                }
                valueClass={
                  result.moe_routing_overhead_pct > 0 ? "text-amber-600" : ""
                }
              />
            )}
          </Section>
        )}

        {/* Multi-tenancy (only when non-dedicated) */}
        {result.tenancy_mode_applied && (
          <Section
            icon={<Users className="h-3.5 w-3.5" />}
            title="Multi-tenancy"
            tooltip={
              <>
                <strong>MIG</strong> divides the GPU into hardware partitions; NVLink between instances is disabled (TP forced to 1) and per-tenant memory + bandwidth are scaled by the profile&apos;s slice size. <strong>Run:ai fractional</strong> time-slices the full GPU; per-tenant throughput = aggregate ÷ tenants, with a 5% KV-fragmentation penalty.
              </>
            }
          >
            <Row
              label="Mode"
              value={
                result.tenancy_mode_applied === "mig"
                  ? "MIG (hardware partition)"
                  : result.tenancy_mode_applied === "runai_fractional"
                    ? "Run:ai fractional"
                    : result.tenancy_mode_applied
              }
            />
            {result.tenants_per_gpu != null && (
              <Row label="Tenants / GPU" value={`${result.tenants_per_gpu}×`} />
            )}
            {result.per_tenant_decode_tps != null && (
              <Row
                label="Per-tenant decode"
                value={`${formatNumber(result.per_tenant_decode_tps)} tok/s`}
              />
            )}
            {result.per_tenant_kv_cache_gb != null && (
              <Row
                label="Per-tenant KV cache"
                value={`${result.per_tenant_kv_cache_gb.toFixed(2)} GB`}
              />
            )}
          </Section>
        )}

        {/* Per-user latency */}
        <Section
          icon={<Gauge className="h-3.5 w-3.5" />}
          title="Per-user latency"
          tooltip={
            <>
              <strong>TTFT</strong> = context_length ÷ per-user prefill tok/s. <strong>TPOT</strong> = 1000 ÷ per-user decode tok/s. Aggregate throughput is divided by concurrent_users × batch_size to get the per-user view — what one user actually feels at the configured load.
            </>
          }
        >
          <Row
            label="TTFT (time to first token)"
            value={
              result.ttft_ms != null
                ? `${formatNumber(result.ttft_ms)} ms`
                : "—"
            }
          />
          <Row
            label="TPOT (per output token)"
            value={
              result.tpot_ms != null
                ? `${result.tpot_ms.toFixed(1)} ms`
                : "—"
            }
            valueClass={
              result.violation_codes.includes("TPOT_MISSED")
                ? "text-amber-600 font-semibold"
                : ""
            }
          />
          <Row
            label="Per-user decode rate"
            value={
              result.per_user_decode_tps != null
                ? `${formatNumber(result.per_user_decode_tps)} tok/s`
                : "—"
            }
          />
        </Section>

        {/* TCO */}
        <Section
          icon={<Banknote className="h-3.5 w-3.5" />}
          title={`${amortMonths / 12}-Year TCO`}
          tooltip={`CapEx (hardware + network) + OpEx (power, colocation, support, software) over ${amortMonths} months. All figures in USD.`}
          learnMore="tco"
        >
          <Row
            label="CapEx (hardware + network)"
            value={formatCurrency(result.capex_usd)}
          />
          {result.opex_breakdown ? (
            <>
              <Row
                label="↳ Power / month"
                value={formatCurrency(result.opex_breakdown.power_usd)}
                valueClass="text-gray-600"
              />
              {result.opex_breakdown.colocation_usd > 0 && (
                <Row
                  label="↳ Colocation / month"
                  value={formatCurrency(result.opex_breakdown.colocation_usd)}
                  valueClass="text-gray-600"
                />
              )}
              {result.opex_breakdown.hw_support_usd > 0 && (
                <Row
                  label="↳ HW support / month"
                  value={formatCurrency(result.opex_breakdown.hw_support_usd)}
                  valueClass="text-gray-600"
                />
              )}
              {result.opex_breakdown.software_usd > 0 && (
                <Row
                  label="↳ Software / month"
                  value={formatCurrency(result.opex_breakdown.software_usd)}
                  valueClass="text-gray-600"
                />
              )}
              <Row
                label="OpEx total / month"
                value={formatCurrency(monthlyOpex)}
              />
            </>
          ) : (
            <Row
              label="OpEx / month"
              value={formatCurrency(monthlyOpex)}
            />
          )}
          <Row
            label="Amortised cost / month"
            value={formatCurrency(monthlyAmortised)}
          />
          <Row
            label={`Total ${amortMonths}-mo TCO`}
            value={formatCurrency(result.tco_usd)}
            valueClass="font-semibold text-gray-900"
          />
          {result.carbon_kg_per_year != null && (
            <Row
              label="Carbon (kg CO₂e / year)"
              value={`${formatNumber(result.carbon_kg_per_year)} kg`}
              valueClass="text-gray-600"
            />
          )}
        </Section>

        {/* Throughput economics */}
        <Section
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          title="Throughput economics"
          tooltip="Tokens/$/mo divides aggregate decode by amortised monthly cost — a value-per-dollar metric that often flips rankings vs raw throughput."
          learnMore="tco"
        >
          <Row
            label="Decode (aggregate)"
            value={`${formatNumber(result.decode_tokens_per_sec)} tok/s`}
          />
          <Row
            label="Prefill (aggregate)"
            value={`${formatNumber(result.prefill_tokens_per_sec)} tok/s`}
          />
          <Row
            label="Tokens / $ / month"
            value={formatNumber(result.tokens_per_usd)}
            valueClass="text-emerald-600 font-semibold"
          />
        </Section>

        {/* Power summary line */}
        {r && (
          <div className="flex items-center gap-1.5 rounded-md bg-gray-50 px-3 py-2 text-[11px] text-gray-600">
            <Zap className="h-3 w-3 text-gray-400" />
            <span>
              CapEx amortised ≈ <strong>{formatCurrency(monthlyCapexShare)}</strong>/mo;
              power dominates above ~{((monthlyOpex / monthlyAmortised) * 100).toFixed(0)}% of run cost.
            </span>
          </div>
        )}

        {/* Advisories */}
        {(advisoryCodes.length > 0 || result.warnings.length > 0) && (
          <div className="space-y-1 border-t border-gray-100 pt-3">
            {advisoryCodes.map((code) => {
              const meta = CODE_LABELS[code];
              return (
                <div
                  key={code}
                  className={`flex items-center gap-1.5 text-[11px] ${
                    meta.tone === "warn" ? "text-amber-700" : "text-blue-700"
                  }`}
                >
                  <AlertTriangle className="h-3 w-3" />
                  <span>{meta.label}</span>
                </div>
              );
            })}
            {result.warnings
              .filter((w) => !w.toLowerCase().includes("specs are estimated"))
              .slice(0, 3)
              .map((w, i) => (
                <div key={i} className="text-[10px] text-gray-500 leading-tight">
                  · {w}
                </div>
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Section({
  icon,
  title,
  children,
  tooltip,
  learnMore,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  tooltip?: React.ReactNode;
  learnMore?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
        {icon} {title}
        {tooltip && (
          <InfoTooltip learnMore={learnMore} iconClassName="h-2.5 w-2.5">
            {tooltip}
          </InfoTooltip>
        )}
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function Row({
  label,
  value,
  valueClass = "",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-[11px]">
      <span className="text-gray-500">{label}</span>
      <span className={`font-mono text-gray-900 ${valueClass}`}>{value}</span>
    </div>
  );
}
