"use client";

import { useState } from "react";
import { useStore } from "@/lib/store";
import { REGION_OPTIONS, REGION_PRESETS, type Region } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { NumericInput } from "@/components/ui/numeric-input";
import { Slider } from "@/components/ui/slider";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

const WEIGHT_KEYS = [
  {
    key: "performance",
    label: "Performance",
    color: "bg-blue-600",
    tooltip: "Aggregate decode tokens/sec. Higher → favours fast GPUs (B300, GB300 NVL72) regardless of price.",
  },
  {
    key: "cost",
    label: "Cost",
    color: "bg-emerald-600",
    tooltip: "36-month TCO (CapEx + OpEx). Higher → favours cheap GPUs that meet the workload (RTX PRO 6000 BSE, AMD MI series).",
  },
  {
    key: "complexity",
    label: "Complexity",
    color: "bg-violet-600",
    tooltip: "Software-stack maturity. Higher → favours mature CUDA/NVIDIA stacks; penalises ROCm and rack-scale (NVL72) deployments.",
  },
  {
    key: "availability",
    label: "Availability",
    color: "bg-amber-600",
    tooltip: "Lead time + supply status. Higher → favours in-stock GPUs (H100, H200, MI300X) over pre-GA SKUs.",
  },
] as const;

export default function ConstraintSliders() {
  const { constraints, setConstraints, setMetricWeight } = useStore();
  // Region is a UI affordance over two backend fields (colo + grid intensity).
  // We don't store it in the constraint payload — selecting one just snaps
  // both numeric inputs to the regional preset values.  Detect the active
  // region by matching back to the closest preset, defaulting to US-East.
  const activeRegion: Region =
    (Object.entries(REGION_PRESETS) as [Region, typeof REGION_PRESETS[Region]][]).find(
      ([, p]) =>
        p.colo_usd_per_kw_per_month === constraints.colo_usd_per_kw_per_month &&
        p.grid_carbon_intensity_g_kwh === constraints.grid_carbon_intensity_g_kwh,
    )?.[0] ?? "US-East";
  const [regionDirty, setRegionDirty] = useState(false);

  const applyRegion = (region: Region) => {
    const preset = REGION_PRESETS[region];
    setConstraints({
      colo_usd_per_kw_per_month: preset.colo_usd_per_kw_per_month,
      grid_carbon_intensity_g_kwh: preset.grid_carbon_intensity_g_kwh,
    });
    setRegionDirty(false);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Constraints & Weights</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {/* Budget */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Max Budget ($)
              <InfoTooltip learnMore="constraints">
                Amortised TCO ceiling. GPUs over the limit get a score penalty
                proportional to how badly they exceed it (capped at 90%).
              </InfoTooltip>
            </label>
            <NumericInput
              min={0}
              nullable
              placeholder="No limit"
              value={constraints.max_budget_usd}
              onChange={(v) => setConstraints({ max_budget_usd: v })}
            />
          </div>

          {/* Power */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Max Power/Rack (kW)
              <InfoTooltip learnMore="constraints">
                Per-rack power envelope. GPUs whose rack power exceeds this take a flat 30% score penalty.
              </InfoTooltip>
            </label>
            <NumericInput
              min={0}
              nullable
              placeholder="No limit"
              value={constraints.max_power_per_rack_kw}
              onChange={(v) => setConstraints({ max_power_per_rack_kw: v })}
            />
          </div>

          {/* Cooling */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Cooling Type
              <InfoTooltip learnMore="constraints">
                Air-cooled sites filter out DLC-mandatory GPUs (B300, GB200/GB300 NVL72).
                Choice also picks the PUE used for OpEx (1.15 liquid / 1.30 air).
              </InfoTooltip>
            </label>
            <Select
              value={constraints.cooling_type}
              onValueChange={(v) => setConstraints({ cooling_type: v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="air">Air Cooling</SelectItem>
                <SelectItem value="liquid">Liquid Cooling</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Lead Time */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Max Lead Time (wks)
              <InfoTooltip learnMore="availability">
                Hard cap on procurement wait. GPUs with lead time over the
                limit take a flat 30% score penalty.
              </InfoTooltip>
            </label>
            <NumericInput
              min={0}
              nullable
              placeholder="No limit"
              value={constraints.max_lead_time_weeks}
              onChange={(v) => setConstraints({ max_lead_time_weeks: v })}
            />
          </div>

          {/* Amortisation */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Amortisation (yrs)
              <InfoTooltip learnMore="tco">
                CapEx amortised over this period. Default 4yr. AWS uses 5yr,
                hyperscalers up to 6yr — longer = lower amortised cost / month.
              </InfoTooltip>
            </label>
            <Select
              value={String(constraints.amortization_months)}
              onValueChange={(v) => setConstraints({ amortization_months: +v })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="36">3 years (36 mo)</SelectItem>
                <SelectItem value="48">4 years (48 mo)</SelectItem>
                <SelectItem value="60">5 years (60 mo)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Target TPOT */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Target TPOT (ms)
              <InfoTooltip>
                Target time-per-output-token per user, in milliseconds. Candidates whose per-user TPOT exceeds this raise a TPOT_MISSED advisory — informational only, ranking is unaffected. 50 ms ≈ 20 tok/s/user (chat-fast); 100 ms ≈ 10 tok/s/user (acceptable); 200+ ms feels sluggish.
              </InfoTooltip>
            </label>
            <NumericInput
              min={1}
              nullable
              placeholder="No target"
              value={constraints.target_tpot_ms}
              onChange={(v) => setConstraints({ target_tpot_ms: v })}
            />
          </div>
        </div>

        {/* Region — a UI affordance that snaps colo + grid intensity to a
            preset.  Backend stays region-agnostic; selecting a region just
            updates the two numeric inputs below. */}
        <div className="mt-5 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
              Region
              <InfoTooltip learnMore="tco">
                Snaps Colocation rate and Grid Carbon Intensity to regional defaults (CBRE H2-2025 colo rates + EPA eGRID 2024 / IEA 2024 grid mix). Manual edits to either field below are preserved — Region is just a quick-set.
              </InfoTooltip>
            </label>
            <Select
              value={activeRegion}
              onValueChange={(v) => applyRegion(v as Region)}
            >
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REGION_OPTIONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <span className="pb-2 text-[10px] text-gray-400 max-w-md">
            {REGION_PRESETS[activeRegion].blurb}
            {regionDirty && " (manual override active)"}
          </span>
        </div>

        {/* Run Costs (OpEx components) */}
        <div className="mt-5">
          <span className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
            Run Costs
            <InfoTooltip learnMore="tco">
              Operating-cost components included in the monthly OpEx line.
              Set any to 0 to opt out (e.g. self-operated DC: zero out colo).
              Defaults reflect 2026 US enterprise typical.
            </InfoTooltip>
          </span>
          <div className="mt-3 grid grid-cols-2 gap-4 md:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1 text-[10px] font-medium text-gray-500">
                Colocation ($/IT-kW/mo)
                <InfoTooltip learnMore="tco" iconClassName="h-2.5 w-2.5">
                  Rent for rack space, cooling, UPS, fire suppression. CBRE H2-2025 reports ~$195/kW-mo for 250–500 kW deployments in US DC markets. Charged on IT-kW reserved (separate from metered power).
                </InfoTooltip>
              </label>
              <NumericInput
                min={0}
                fallback={200}
                value={constraints.colo_usd_per_kw_per_month}
                onChange={(v) => {
                  setConstraints({ colo_usd_per_kw_per_month: v ?? 0 });
                  setRegionDirty(true);
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1 text-[10px] font-medium text-gray-500">
                HW Support (% of CapEx/yr)
                <InfoTooltip learnMore="tco" iconClassName="h-2.5 w-2.5">
                  Hardware support contract (Dell ProSupport, NVIDIA Mission Control, NBD on-site replacement). Typical 8–15% of CapEx per year for AI hardware.
                </InfoTooltip>
              </label>
              <NumericInput
                min={0}
                max={100}
                fallback={10}
                value={constraints.hw_support_pct_of_capex_per_year * 100}
                onChange={(v) => setConstraints({ hw_support_pct_of_capex_per_year: (v ?? 0) / 100 })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1 text-[10px] font-medium text-gray-500">
                Software ($/GPU/yr)
                <InfoTooltip learnMore="tco" iconClassName="h-2.5 w-2.5">
                  Software licensing per GPU per year. NVIDIA AI Enterprise list ~$1,000/GPU/yr (5-yr term included free with H100/H200).
                </InfoTooltip>
              </label>
              <NumericInput
                min={0}
                fallback={1000}
                value={constraints.software_usd_per_gpu_per_year}
                onChange={(v) => setConstraints({ software_usd_per_gpu_per_year: v ?? 0 })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1 text-[10px] font-medium text-gray-500">
                Grid CO₂ (g/kWh)
                <InfoTooltip iconClassName="h-2.5 w-2.5">
                  Grid carbon intensity in grams CO₂-equivalent per kWh, used to estimate annual operating emissions on the result. EPA eGRID 2024 / IEA 2024: US-East ~380, US-West (PNW) ~250, EU ~270, APAC (coal-heavy) ~550. Edit directly to override the regional preset.
                </InfoTooltip>
              </label>
              <NumericInput
                min={0}
                max={1500}
                fallback={380}
                value={constraints.grid_carbon_intensity_g_kwh}
                onChange={(v) => {
                  setConstraints({ grid_carbon_intensity_g_kwh: v ?? 0 });
                  setRegionDirty(true);
                }}
              />
            </div>
          </div>
        </div>

        {/* Metric Weights */}
        <div className="mt-5">
          <span className="flex items-center gap-1 text-[11px] font-medium text-gray-500">
            Metric Weights
            <InfoTooltip learnMore="weights">
              Each axis is rank-normalised (0-1) across GPUs and combined as a
              weighted sum. Push a slider toward 100% to weight the
              recommendation entirely on that dimension.
            </InfoTooltip>
          </span>
          <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
            {WEIGHT_KEYS.map(({ key, label, color, tooltip }) => {
              const value = (constraints.metric_weights as Record<string, number>)[key];
              return (
                <div key={key} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1 text-[10px] font-medium text-gray-500">
                      {label}
                      <InfoTooltip learnMore="weights" iconClassName="h-2.5 w-2.5">
                        {tooltip}
                      </InfoTooltip>
                    </span>
                    <span className="font-mono text-[10px] text-gray-400">
                      {(value * 100).toFixed(0)}%
                    </span>
                  </div>
                  <Slider
                    value={[value * 100]}
                    min={0}
                    max={100}
                    step={5}
                    onValueChange={([v]) => setMetricWeight(key, v / 100)}
                    trackColor={color}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
