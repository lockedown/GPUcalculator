"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Trash2, Link as LinkIcon, Check, Pin, Printer } from "lucide-react";
import {
  loadPinned,
  unpinScenario,
  encodePinnedToUrl,
  decodeUrlToPinned,
  importPinned,
  MAX_PINNED,
  type PinnedScenario,
} from "@/lib/scenarios";
import { api } from "@/lib/api";
import type { ComparisonResponse, GPUResult } from "@/types";
import { GPU_COLORS } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatNumber } from "@/lib/utils";

interface ScenarioRow {
  scenario: PinnedScenario;
  comparison: ComparisonResponse | null;
  loading: boolean;
  error: string | null;
}

export default function ScenariosPage() {
  const [rows, setRows] = useState<ScenarioRow[]>([]);
  const [copied, setCopied] = useState(false);

  // First mount: import any URL-shared scenarios, then load + fetch.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const compare = params.get("compare");
    if (compare) {
      const imported = decodeUrlToPinned(compare);
      if (imported.length > 0) {
        importPinned(imported);
        toast.success(`Imported ${imported.length} scenario${imported.length > 1 ? "s" : ""}`, {
          description: "Added to your local pins.",
        });
      }
      // Strip the param so a refresh doesn't re-import.
      window.history.replaceState(null, "", window.location.pathname);
    }
    refresh();
  }, []);

  function refresh() {
    const pinned = loadPinned();
    setRows(pinned.map(s => ({ scenario: s, comparison: null, loading: true, error: null })));

    pinned.forEach((s, i) => {
      api.compare(s.workload, s.constraints)
        .then(comp => {
          setRows(prev => {
            const next = [...prev];
            if (next[i] && next[i].scenario.id === s.id) {
              next[i] = { ...next[i], comparison: comp, loading: false };
            }
            return next;
          });
        })
        .catch((e: Error) => {
          setRows(prev => {
            const next = [...prev];
            if (next[i] && next[i].scenario.id === s.id) {
              next[i] = { ...next[i], loading: false, error: e.message };
            }
            return next;
          });
        });
    });
  }

  function handleUnpin(id: string) {
    unpinScenario(id);
    refresh();
    toast.success("Scenario removed");
  }

  async function handleCopyComparisonLink() {
    if (typeof window === "undefined") return;
    const pinned = loadPinned();
    if (pinned.length === 0) {
      toast.error("No scenarios pinned yet.");
      return;
    }
    const encoded = encodePinnedToUrl(pinned);
    const url = `${window.location.origin}/scenarios?compare=${encoded}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success("Comparison link copied", {
        description: `${pinned.length} scenario${pinned.length > 1 ? "s" : ""} encoded — anyone with this URL imports them.`,
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Couldn't copy — your browser blocked clipboard access.");
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-gray-900">Scenario Comparison</h1>
          <p className="mt-1 text-sm text-gray-500">
            Pin up to {MAX_PINNED} configurations from the dashboard and compare them side-by-side.
            Pins are stored locally in your browser; share via the link button.
          </p>
        </div>
        {rows.length > 0 && (
          <div className="flex shrink-0 items-center gap-2 print-hide">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyComparisonLink}
              title="Copy a URL that imports all current pins into the recipient's browser"
            >
              {copied ? (
                <><Check className="h-3.5 w-3.5" /> Copied</>
              ) : (
                <><LinkIcon className="h-3.5 w-3.5" /> Copy comparison link</>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => typeof window !== "undefined" && window.print()}
              title="Print or save the side-by-side comparison as PDF"
            >
              <Printer className="h-3.5 w-3.5" /> Print / PDF
            </Button>
          </div>
        )}
      </div>

      {/* Empty state */}
      {rows.length === 0 ? (
        <Card>
          <CardContent className="flex h-64 flex-col items-center justify-center gap-3 text-center text-sm text-gray-500">
            <Pin className="h-8 w-8 text-gray-300" />
            <div>No scenarios pinned yet.</div>
            <Button asChild size="sm">
              <Link href="/">Go to dashboard → Pin scenario</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div
          className="grid gap-4 print-scenarios-grid"
          style={{ gridTemplateColumns: `repeat(${rows.length}, minmax(0, 1fr))` }}
        >
          {rows.map((row) => (
            <ScenarioCard key={row.scenario.id} row={row} onRemove={handleUnpin} />
          ))}
        </div>
      )}

      {rows.length > 0 && rows.length < MAX_PINNED && (
        <p className="text-xs text-gray-500 text-center">
          {rows.length} of {MAX_PINNED} pinned. <Link href="/" className="text-blue-600 hover:underline">Pin another from the dashboard →</Link>
        </p>
      )}
    </div>
  );
}

function ScenarioCard({ row, onRemove }: { row: ScenarioRow; onRemove: (id: string) => void }) {
  const { scenario, comparison, loading, error } = row;
  const sweet = comparison?.results.find(r => r.gpu_name === comparison.sweet_spot_gpu) ?? comparison?.results[0] ?? null;

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-3">
        <CardTitle className="truncate text-sm">{scenario.name}</CardTitle>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0 text-gray-400 hover:text-rose-600"
          onClick={() => onRemove(scenario.id)}
          title="Remove this pin"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-[12px]">
        {/* Inputs summary */}
        <Section title="Inputs">
          <Row label="Model" value={`${scenario.workload.model_params_b}B ${scenario.workload.precision}`} />
          <Row label="Context" value={`${(scenario.workload.context_length / 1024).toFixed(0)}K`} />
          <Row label="Users" value={`${scenario.workload.concurrent_users}`} />
          <Row label="Cooling" value={scenario.constraints.cooling_type} />
          <Row label="Amortise" value={`${scenario.constraints.amortization_months / 12} yr`} />
        </Section>

        {/* Result */}
        {loading ? (
          <Section title="Sweet Spot">
            <Skeleton className="h-5 w-32 mb-2" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
          </Section>
        ) : error ? (
          <Section title="Result">
            <div className="text-rose-600">Failed to load: {error}</div>
          </Section>
        ) : sweet ? (
          <>
            <Section title="Sweet Spot">
              <div
                className="text-sm font-bold"
                style={{ color: GPU_COLORS[sweet.gpu_name] || "#111" }}
              >
                {sweet.gpu_name}
              </div>
              <Row label="GPUs" value={`${sweet.topology?.gpu_count ?? "—"}× ${sweet.topology?.parallelism_strategy ?? ""}`} />
              <Row label="Score" value={sweet.composite_score?.toFixed(3) ?? "—"} />
            </Section>

            <Section title="Throughput">
              <Row label="Decode" value={`${formatNumber(sweet.decode_tokens_per_sec)} tok/s`} />
              <Row label="Prefill" value={`${formatNumber(sweet.prefill_tokens_per_sec)} tok/s`} />
              <Row label="Tokens / $ / mo" value={formatNumber(sweet.tokens_per_usd)} />
            </Section>

            <Section title="Cost">
              <Row label="CapEx" value={formatCurrency(sweet.capex_usd)} />
              <Row label="OpEx / mo" value={formatCurrency(sweet.opex_monthly_usd)} />
              <Row
                label={`${scenario.constraints.amortization_months / 12}-yr TCO`}
                value={formatCurrency(sweet.tco_usd)}
                emphasis
              />
            </Section>

            {sweet.violation_codes.length > 0 && (
              <Section title="Advisories">
                {sweet.violation_codes.map(c => (
                  <div key={c} className="text-[11px] text-amber-700">{c}</div>
                ))}
              </Section>
            )}

            {/* Top-3 alternates */}
            {comparison && comparison.results.length > 1 && (
              <Section title="Top alternatives">
                {comparison.results.slice(1, 4).map((r: GPUResult) => (
                  <Row
                    key={r.gpu_id}
                    label={r.gpu_name}
                    value={`${r.composite_score?.toFixed(3)} · ${formatCurrency(r.tco_usd)}`}
                  />
                ))}
              </Section>
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-gray-100 pt-2 first:border-t-0 first:pt-0">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-gray-500">{title}</div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function Row({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-[11px]">
      <span className="text-gray-500">{label}</span>
      <span className={`font-mono ${emphasis ? "font-semibold text-gray-900" : "text-gray-900"}`}>{value}</span>
    </div>
  );
}
