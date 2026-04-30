"use client";

import { useStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { NumericInput } from "@/components/ui/numeric-input";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

const WEIGHT_KEYS = [
  { key: "performance", label: "Performance", color: "bg-blue-600" },
  { key: "cost", label: "Cost", color: "bg-emerald-600" },
  { key: "complexity", label: "Complexity", color: "bg-violet-600" },
  { key: "availability", label: "Availability", color: "bg-amber-600" },
] as const;

export default function ConstraintSliders() {
  const { constraints, setConstraints, setMetricWeight } = useStore();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Constraints & Weights</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {/* Budget */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-medium text-gray-500">Max Budget (£)</label>
            <NumericInput
              min={0}
              nullable
              placeholder="No limit"
              value={constraints.max_budget_gbp}
              onChange={(v) => setConstraints({ max_budget_gbp: v })}
            />
          </div>

          {/* Power */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-medium text-gray-500">Max Power/Rack (kW)</label>
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
            <label className="text-[11px] font-medium text-gray-500">Cooling Type</label>
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
            <label className="text-[11px] font-medium text-gray-500">Max Lead Time (wks)</label>
            <NumericInput
              min={0}
              nullable
              placeholder="No limit"
              value={constraints.max_lead_time_weeks}
              onChange={(v) => setConstraints({ max_lead_time_weeks: v })}
            />
          </div>
        </div>

        {/* Metric Weights */}
        <div className="mt-5">
          <span className="text-[11px] font-medium text-gray-500">Metric Weights</span>
          <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
            {WEIGHT_KEYS.map(({ key, label, color }) => {
              const value = (constraints.metric_weights as Record<string, number>)[key];
              return (
                <div key={key} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-medium text-gray-500">{label}</span>
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
