import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = {
  title: "API — GPU Deployment Optimizer",
  description:
    "Public REST API for the GPU sizing engine. curl-friendly endpoints for hardware catalogue, sizing comparisons, prices, and CSV export.",
};

const API_BASE = "https://gpu-calc-api.vercel.app/api";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "auth", label: "Auth & rate limits" },
  { id: "hardware", label: "Hardware" },
  { id: "compare", label: "Sizing & compare" },
  { id: "benchmarks", label: "Benchmarks" },
  { id: "prices", label: "Prices" },
  { id: "networking", label: "Networking" },
  { id: "export", label: "Export" },
  { id: "fields", label: "Key response fields" },
  { id: "openapi", label: "OpenAPI spec" },
];

export default function ApiDocsPage() {
  return (
    <div className="grid gap-8 xl:grid-cols-[220px_1fr]">
      <aside className="hidden xl:block">
        <div className="sticky top-20 space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 mb-3">
            On this page
          </div>
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="block rounded-md px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            >
              {s.label}
            </a>
          ))}
        </div>
      </aside>

      <article className="max-w-3xl space-y-8">
        <header>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">API</h1>
          <p className="mt-2 text-sm text-gray-600">
            Everything the dashboard does is available as a public REST API
            you can call directly from your own apps, scripts, or notebooks.
            Same engine, same data, same calibration.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Badge variant="success" className="rounded-full">Public</Badge>
            <Badge variant="default" className="rounded-full">No auth</Badge>
            <Badge variant="default" className="rounded-full">JSON in / JSON out</Badge>
            <code className="rounded bg-gray-100 px-2 py-0.5 font-mono">{API_BASE}</code>
          </div>
        </header>

        {/* Overview */}
        <Section id="overview" title="Overview">
          <p>
            The API is a thin FastAPI server in front of a Postgres catalogue
            of NVIDIA + AMD GPUs. Every endpoint returns JSON, accepts JSON
            request bodies (where applicable), and uses standard HTTP status
            codes. There&apos;s no SDK — pick your preferred HTTP client.
          </p>
          <p>
            Try anything by pasting the curl examples below into a terminal.
            Every example here is hitting production.
          </p>
        </Section>

        {/* Auth + rate limits */}
        <Section id="auth" title="Auth & rate limits">
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>No authentication.</strong> All endpoints are open. If
              that ever changes we&apos;ll publish key issuance here.
            </li>
            <li>
              <strong>Rate limits.</strong> Vercel&apos;s default per-IP
              throttling applies (multiple thousands of requests per minute
              before you&apos;ll see 429s). For sustained scripted use,
              cache the catalogue endpoints (they change at most quarterly)
              and only re-call <code>/api/compare</code> when inputs change.
            </li>
            <li>
              <strong>CORS.</strong> Restricted to the dashboard origin. If
              you&apos;re calling from server-side code (curl, Python
              <code>requests</code>, Node fetch on a server) CORS doesn&apos;t
              apply. Browser JS from third-party domains is blocked — file an
              issue if you need an allowlist entry.
            </li>
            <li>
              <strong>Versioning.</strong> Field names follow the conventions
              you see today (snake_case, USD-denominated cost fields,
              <code>opex_breakdown</code>, <code>violation_codes</code>).
              Additive changes only on the response shape; breaking changes
              would be flagged in the methodology page release notes.
            </li>
          </ul>
        </Section>

        {/* Hardware */}
        <Section id="hardware" title="Hardware catalogue">
          <Endpoint
            method="GET"
            path="/api/hardware"
            desc="List every GPU with full spec metadata (memory, bandwidth, TFLOPS, MSRP, cooling, interconnect)."
            curl={`curl ${API_BASE}/hardware`}
          />
          <Endpoint
            method="GET"
            path="/api/hardware?vendor=NVIDIA"
            desc="Filter by vendor (NVIDIA or AMD)."
            curl={`curl '${API_BASE}/hardware?vendor=NVIDIA'`}
          />
          <Endpoint
            method="GET"
            path="/api/hardware/{gpu_id}"
            desc="Detail view including benchmark scores and supply data."
            curl={`curl ${API_BASE}/hardware/4`}
          />
        </Section>

        {/* Compare */}
        <Section id="compare" title="Sizing & compare">
          <p>
            The headline endpoint. Send a workload + constraint payload, get
            back every GPU evaluated and ranked, with the sweet-spot pick
            flagged.
          </p>
          <Endpoint
            method="POST"
            path="/api/compare"
            desc="Full multi-GPU comparison with sweet-spot selection."
            curl={`curl -X POST ${API_BASE}/compare \\
  -H 'Content-Type: application/json' \\
  -d '{
    "workload": {
      "model_params_b": 70,
      "precision": "FP8",
      "context_length": 16384,
      "concurrent_users": 50,
      "workload_type": "inference"
    },
    "constraints": {
      "cooling_type": "liquid",
      "max_budget_usd": 500000,
      "amortization_months": 48,
      "metric_weights": {
        "performance": 0.4,
        "cost": 0.4,
        "complexity": 0.1,
        "availability": 0.1
      }
    }
  }'`}
          />
          <Endpoint
            method="POST"
            path="/api/calculate"
            desc="Same engine but returns a flat list (no sweet-spot meta). Prefer /compare for most cases."
            curl={`curl -X POST ${API_BASE}/calculate \\
  -H 'Content-Type: application/json' \\
  -d '{"workload": {"model_params_b": 70}, "constraints": {}}'`}
          />
          <p className="text-[11px] text-gray-500">
            Full request schema:{" "}
            <a className="text-blue-600 hover:underline" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
              Swagger UI
            </a>
            . The dashboard&apos;s URL share format is a one-to-one mapping of these fields — see{" "}
            <Link href="/methodology#weights" className="text-blue-600 hover:underline">methodology</Link>.
          </p>
        </Section>

        {/* Benchmarks */}
        <Section id="benchmarks" title="Benchmarks">
          <Endpoint
            method="GET"
            path="/api/benchmarks"
            desc="All benchmark scores (9 GPUs × 21 benchmark types from the Finance GPU Benchmark Matrix)."
            curl={`curl ${API_BASE}/benchmarks`}
          />
          <Endpoint
            method="GET"
            path="/api/benchmarks?category=tokenization"
            desc="Filter by workload category: quant, risk, inference, hpc, trading, tokenization."
            curl={`curl '${API_BASE}/benchmarks?category=tokenization'`}
          />
          <Endpoint
            method="GET"
            path="/api/benchmarks/{category}"
            desc="Path-style category filter (same data)."
            curl={`curl ${API_BASE}/benchmarks/quant`}
          />
        </Section>

        {/* Prices */}
        <Section id="prices" title="Prices">
          <Endpoint
            method="GET"
            path="/api/prices"
            desc="Per-GPU price-history trajectories (USD). Useful for trend charts."
            curl={`curl ${API_BASE}/prices`}
          />
          <Endpoint
            method="GET"
            path="/api/prices/{gpu_id}"
            desc="Single GPU's price trajectory."
            curl={`curl ${API_BASE}/prices/4`}
          />
        </Section>

        {/* Networking */}
        <Section id="networking" title="Networking">
          <Endpoint
            method="GET"
            path="/api/networking"
            desc="Catalogue of intra-node + inter-node fabric options (NVLink, IB NDR/XDR, Infinity Fabric, RoCEv2)."
            curl={`curl ${API_BASE}/networking`}
          />
        </Section>

        {/* Export */}
        <Section id="export" title="Export">
          <Endpoint
            method="POST"
            path="/api/export/csv"
            desc="Run a comparison and stream the result as CSV (one row per GPU)."
            curl={`curl -X POST ${API_BASE}/export/csv \\
  -H 'Content-Type: application/json' \\
  -d '{"model_params_b": 70, "precision": "FP8"}' \\
  -o gpu_comparison.csv`}
          />
          <Endpoint
            method="POST"
            path="/api/export/json"
            desc="Same as /compare but with a generated_at timestamp + workload echo, suited for archival."
            curl={`curl -X POST ${API_BASE}/export/json \\
  -H 'Content-Type: application/json' \\
  -d '{"model_params_b": 70}'`}
          />
        </Section>

        {/* Field reference */}
        <Section id="fields" title="Key response fields">
          <p>The most-consulted fields on a <code>/api/compare</code> result:</p>
          <Defs items={[
            { term: "sweet_spot_gpu", def: "string — name of the highest-scoring GPU that passes all hard constraints. Falls back to overall top scorer if nothing passes." },
            { term: "results[].composite_score", def: "0-1 weighted composite. Already applies any constraint penalties." },
            { term: "results[].tco_usd", def: "Total Cost of Ownership over the configured amortisation period (USD)." },
            { term: "results[].capex_usd", def: "Hardware + network up-front cost (USD)." },
            { term: "results[].opex_monthly_usd", def: "Sum of the four OpEx lines per month (USD)." },
            { term: "results[].opex_breakdown", def: "Itemised monthly OpEx: { power_usd, colocation_usd, hw_support_usd, software_usd }." },
            { term: "results[].tokens_per_usd", def: "Aggregate decode tokens / amortised $ / month — value-per-dollar." },
            { term: "results[].decode_tokens_per_sec", def: "Memory-bandwidth-bound aggregate across all DP replicas, calibrated against L3-70B benchmark." },
            { term: "results[].prefill_tokens_per_sec", def: "Compute-bound (with O(L) attention term applied) aggregate across replicas." },
            { term: "results[].topology", def: "{ gpu_count, nodes, gpus_per_node, parallelism_strategy, tp_degree, pp_degree, dp_degree, … }" },
            { term: "results[].rack_plan", def: "{ total_racks, gpus_per_rack, pdu_tier, power_per_rack_kw, cooling_capacity_kw, fits_cooling, … }" },
            { term: "results[].violation_codes", def: "string[] — stable codes for constraints/advisories (BUDGET_EXCEEDED, COOLING_HARD/SOFT, DLC_REQUIRED, MARGINAL_AIR_COOLING, PRE_GA, etc.). Drive your own filter UIs from these instead of warning-text matching." },
          ]} />
        </Section>

        {/* OpenAPI */}
        <Section id="openapi" title="OpenAPI spec">
          <p>FastAPI auto-generates a complete OpenAPI 3 spec from the schemas:</p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <a className="text-blue-600 hover:underline" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
                Swagger UI
              </a>{" "}
              — interactive try-it-out browser
            </li>
            <li>
              <a className="text-blue-600 hover:underline" href={`${API_BASE}/openapi.json`} target="_blank" rel="noreferrer">
                openapi.json
              </a>{" "}
              — raw spec, feed it into your codegen of choice (openapi-generator, oapi-codegen, etc.)
            </li>
          </ul>
        </Section>

        <footer className="border-t border-gray-200 pt-6 mt-8 text-xs">
          <Link href="/" className="text-blue-600 hover:underline">← Back to dashboard</Link>
          <span className="mx-2 text-gray-400">·</span>
          <Link href="/methodology" className="text-blue-600 hover:underline">Methodology →</Link>
        </footer>
      </article>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <Card id={id} className="scroll-mt-20">
      <CardHeader>
        <CardTitle>
          <a href={`#${id}`} className="hover:underline">{title}</a>
        </CardTitle>
      </CardHeader>
      <CardContent className="text-gray-700 space-y-3 [&_p]:text-sm [&_li]:text-sm [&_code]:text-[11px] [&_code]:bg-gray-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded">
        {children}
      </CardContent>
    </Card>
  );
}

function Endpoint({
  method,
  path,
  desc,
  curl,
}: {
  method: "GET" | "POST";
  path: string;
  desc: string;
  curl: string;
}) {
  const methodColour =
    method === "GET" ? "bg-emerald-100 text-emerald-700" : "bg-blue-100 text-blue-700";
  return (
    <div className="rounded-md border border-gray-200 p-3 space-y-2">
      <div className="flex items-center gap-2 font-mono text-[11px]">
        <span className={`rounded px-1.5 py-0.5 font-semibold ${methodColour}`}>{method}</span>
        <code className="bg-gray-100 px-1.5 py-0.5 rounded">{path}</code>
      </div>
      <p className="text-[12px] text-gray-600">{desc}</p>
      <pre className="overflow-x-auto rounded bg-gray-900 px-3 py-2 text-[10.5px] leading-snug text-gray-100">
        {curl}
      </pre>
    </div>
  );
}

function Defs({ items }: { items: { term: string; def: string }[] }) {
  return (
    <dl className="space-y-2 my-2">
      {items.map((it) => (
        <div key={it.term} className="grid grid-cols-[200px_1fr] gap-3 text-sm">
          <dt className="font-mono text-[11px] text-gray-900 self-baseline">{it.term}</dt>
          <dd className="text-gray-600 text-[12px]">{it.def}</dd>
        </div>
      ))}
    </dl>
  );
}
