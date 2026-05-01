import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Methodology — GPU Deployment Optimizer",
  description:
    "How the optimizer derives sizing, TCO, complexity, availability, and the sweet-spot recommendation.",
};

const SECTIONS = [
  { id: "inputs", label: "Inputs" },
  { id: "topology", label: "Topology & GPU count" },
  { id: "performance", label: "Performance (decode & prefill)" },
  { id: "tco", label: "TCO (CapEx + OpEx)" },
  { id: "complexity", label: "Complexity score" },
  { id: "availability", label: "Availability score" },
  { id: "constraints", label: "Constraints" },
  { id: "weights", label: "Weights & sweet-spot ranking" },
  { id: "caveats", label: "Caveats & known limits" },
];

export default function MethodologyPage() {
  return (
    <div className="grid gap-8 xl:grid-cols-[220px_1fr]">
      {/* Sticky table of contents */}
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
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Methodology</h1>
          <p className="mt-2 text-sm text-gray-600">
            How the optimizer turns your workload and constraints into a GPU
            recommendation, a topology, an amortised TCO, and a sweet-spot pick.
            All formulas live in <code className="text-[11px] bg-gray-100 px-1 py-0.5 rounded">backend/app/engine/</code>;
            this page summarises the behaviour without burying you in source.
          </p>
        </header>

        {/* Inputs */}
        <Section id="inputs" title="Inputs">
          <p>
            The dashboard drives everything from a single workload + constraint
            payload. The fields and what they mean:
          </p>
          <Defs items={[
            { term: "Model size (B params)", def: "Total parameter count of the model in billions. Drives memory footprint, compute load, and KV-cache size." },
            { term: "Precision", def: "Numeric format used at inference time. FP16/BF16 are 2 bytes/param; FP8 is 1 byte/param; FP4 is 0.5 bytes/param. Lower precision halves memory and roughly doubles throughput on supporting hardware." },
            { term: "Context length", def: "Maximum input + output tokens per request. KV cache memory grows linearly with context length." },
            { term: "Concurrent users", def: "Number of independent requests in flight at once. Drives KV-cache total and forces additional data-parallel replicas when throughput per user falls below 10 tok/s." },
            { term: "Workload type", def: "Inference / training / fine-tuning / specialised finance categories. Acts as a hard filter — the inference-only RTX PRO 6000 BSE is excluded from training jobs, for example." },
            { term: "Mixture-of-Experts (MoE)", def: "If checked, only a fraction of the total experts activate per token. Memory still holds all experts; compute and bandwidth scale with active fraction." },
            { term: "Cooling type", def: "Air or liquid. Air-only sites filter out DLC-mandatory GPUs (B300, GB200/GB300 NVL72) entirely." },
            { term: "Max budget / power / lead time", def: "Optional hard limits. GPUs that exceed them get a 30% score penalty per violation (capped at 90% so they don't disappear from the table)." },
          ]} />
        </Section>

        {/* Topology */}
        <Section id="topology" title="Topology & GPU count">
          <p>
            For each candidate GPU the engine sizes the smallest deployment
            that can both hold the model + KV cache and meet a minimum
            per-user throughput target.
          </p>
          <ol className="list-decimal pl-5 space-y-2 marker:text-gray-400">
            <li>
              <strong>Model fit.</strong> <code className="bg-gray-100 px-1 rounded text-[11px]">model_memory_gb = params × bytes_per_param</code>.
              Minimum GPUs to hold the model = <code className="bg-gray-100 px-1 rounded text-[11px]">⌈model_memory ÷ (single_GPU_VRAM × 0.85)⌉</code>.
              The 0.85 keeps 15% headroom for activations and buffers.
            </li>
            <li>
              <strong>Throughput-aware DP.</strong> Each user must hit at
              least 10 tok/s. Required throughput = <code className="bg-gray-100 px-1 rounded text-[11px]">users × 10</code>;
              data-parallel replicas = <code className="bg-gray-100 px-1 rounded text-[11px]">⌈required ÷ per-replica throughput⌉</code>.
            </li>
            <li>
              <strong>Per-replica memory check.</strong> Each replica only
              handles its share of users, so KV cache scales with
              <code className="bg-gray-100 px-1 rounded text-[11px]">⌈users ÷ DP⌉ × per-user-KV</code>.
              Capacity is sized against per-replica memory, not total.
            </li>
            <li>
              <strong>Round TP up to a power of 2.</strong> NCCL all-reduce
              is most efficient at TP ∈ {"{1, 2, 4, 8}"}; odd values are rare in
              production.
            </li>
            <li>
              <strong>Multi-node penalty.</strong> Above 8 GPUs per node, the
              engine adds pipeline parallelism and applies a 5% throughput
              penalty per additional node (capped at 50%) to reflect cross-node
              IB latency.
            </li>
          </ol>
          <p>
            <strong>Per-user KV cache</strong> uses GQA-aware sizing:
            <code className="bg-gray-100 px-1 rounded text-[11px]">
              {" "}2 × num_layers × (num_KV_heads × head_dim) × context × bytes_per_elem
            </code>.
            For Llama-3-70B in FP16 at 16 K context that's ~5 GiB per user; at 4 K it's ~1.25 GiB.
          </p>
        </Section>

        {/* Performance */}
        <Section id="performance" title="Performance (decode & prefill)">
          <p>
            LLM inference has two phases. <strong>Prefill</strong> processes
            the entire prompt in parallel — compute-bound. <strong>Decode</strong>{" "}
            generates one token at a time and has to stream all the model
            weights through the GPU per token — memory-bandwidth-bound.
          </p>
          <Defs items={[
            { term: "Decode (per GPU)", def: "BW ÷ (model_bytes + L × per-token-KV-bytes). At short context (4K) the KV term is ~1% of model so decode is essentially BW ÷ model_bytes. At 128K context the KV-read term is ~30% of model and decode slows accordingly." },
            { term: "Prefill (per GPU)", def: "min(compute_limit, mem_limit). compute_limit = effective_TFLOPS ÷ (2N + 2 × num_layers × hidden_dim × L) — the 2N is FFN/projections, the second term is attention O(L). mem_limit = BW × L ÷ model_bytes — weights stream once per prompt and amortise over L tokens, so prefill is essentially never memory-bound at any reasonable context length." },
            { term: "Calibration", def: "The naive roofline misses kernel optimisations, attention fusion, and tensor-core utilisation. The engine applies a per-GPU multiplier so its prediction matches published Llama-3-70B benchmarks at the 4K reference context within ±15%." },
            { term: "FP8 / FP4 handling", def: "The bytes-per-param + TFLOPS multiplier already encode the precision speed-up. Calibration applies only a residual down-correction for hardware with weak FP8 (e.g. AMD MI300X gets 0.5×)." },
            { term: "Aggregate throughput", def: "Per-replica throughput × number of DP replicas." },
          ]} />
        </Section>

        {/* TCO */}
        <Section id="tco" title="TCO (CapEx + OpEx)">
          <p>
            Total Cost of Ownership over the configured <strong>amortisation
            period</strong> (3 / 4 / 5 years; default 4), in US dollars. All
            prices in the catalogue (GPU MSRPs, network fabric, electricity)
            are denominated in USD; no FX conversion is applied.
          </p>
          <p>
            <strong>Amortisation choice matters.</strong> Hyperscalers have
            been extending GPU useful life as the AI hardware cycle slows:
            AWS uses 5yr, Meta 5.5yr, Google/Oracle 6yr. We default to 4yr as
            an enterprise middle ground, but bump to 5yr if your finance team
            uses a longer depreciation schedule — the per-month amortised
            cost drops proportionally.
          </p>
          <h3 className="text-sm font-semibold text-gray-900 mt-3">CapEx</h3>
          <ul className="list-disc pl-5 space-y-1">
            <li><code className="bg-gray-100 px-1 rounded text-[11px]">gpu_price_USD × gpu_count</code></li>
            <li>+ network fabric cost (all-in per host port: switch slice + NIC + optics)</li>
            <li>+ optional storage cost</li>
          </ul>
          <h3 className="text-sm font-semibold text-gray-900 mt-3">OpEx (monthly)</h3>
          <p>OpEx is the sum of four components, each editable in the dashboard's <em>Run Costs</em> panel and itemised in the Sweet Spot Detail breakdown:</p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <strong>Power</strong> — <code className="bg-gray-100 px-1 rounded text-[11px]">total_TDP_kW × PUE × 730 h × $0.10/kWh</code>.
              The $0.10/kWh default targets a US enterprise self-operated
              cluster — sits above wholesale (NoVA / Phoenix / Dallas average
              $0.057–$0.068/kWh) and below colocation retail (~$0.27/kWh).
              EIA national industrial average is ~$0.085/kWh.
            </li>
            <li>
              <strong>Colocation</strong> — <code className="bg-gray-100 px-1 rounded text-[11px]">total_TDP_kW × $200/kW/month</code>.
              Rent for the rack space, cooling distribution, UPS, fire
              suppression. CBRE H2-2025 reports ~$195/kW-month for 250–500 kW
              deployments in major US DC markets. Charged on IT-kW reserved
              (separate from the metered electricity above). Set to 0 if
              you're self-operated and the rent is already capitalised.
            </li>
            <li>
              <strong>Hardware support</strong> — <code className="bg-gray-100 px-1 rounded text-[11px]">CapEx × 10% / 12</code>.
              Support contract (Dell ProSupport, NVIDIA Mission Control,
              NBD on-site replacement). Typical 8–15% of CapEx per year for
              AI hardware.
            </li>
            <li>
              <strong>Software</strong> — <code className="bg-gray-100 px-1 rounded text-[11px]">gpu_count × $1000/yr / 12</code>.
              Software licensing per GPU per year. NVIDIA AI Enterprise list is
              ~$1,000/GPU/yr (5-yr term included free with H100/H200).
            </li>
          </ul>
          <p>
            <strong>PUE</strong> (Power Usage Effectiveness) sits inside the
            power line and accounts for facility overhead beyond the GPUs
            themselves — cooling, UPS losses, networking, lighting. The engine
            picks 1.15 for liquid-cooled pods and 1.40 for air-cooled
            enterprise sites.
          </p>
          <h3 className="text-sm font-semibold text-gray-900 mt-3">Total</h3>
          <p>
            <code className="bg-gray-100 px-1 rounded text-[11px]">
              TCO = CapEx + (OpEx_monthly × amortisation_months)
            </code>
          </p>
          <p>
            <strong>Tokens per $ per month</strong> divides aggregate
            throughput by the monthly amortised cost — a value-per-dollar
            metric that often flips rankings vs raw throughput.
          </p>
        </Section>

        {/* Complexity */}
        <Section id="complexity" title="Complexity score">
          <p>
            A 0–10 score (higher = easier) capturing how mature and battle-tested
            the GPU's software / deployment stack is.
          </p>
          <p>
            Base = best vendor stack maturity from the database. Today:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>NVIDIA</strong> — CUDA + TensorRT-LLM scores <strong>9/10</strong> (industry-standard, full FP8 Transformer Engine).</li>
            <li><strong>AMD</strong> — ROCm + vLLM scores <strong>6/10</strong> (rapidly improving but smaller ecosystem, more debugging headaches).</li>
          </ul>
          <p>Penalties applied on top:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>FP8 requested but stack has no support: <strong>−2</strong></li>
            <li>FP8 requested but stack has partial support: <strong>−1</strong></li>
            <li>Rack-scale deployment (NVL72): <strong>−2</strong> (specialised power/cooling/handling)</li>
          </ul>
          <p>
            Cooling mismatches are <em>not</em> penalised here — they're
            handled by the optimizer's structured constraint codes so they
            only count once.
          </p>
        </Section>

        {/* Availability */}
        <Section id="availability" title="Availability score">
          <p>
            A 0–1 score driven by lead time and supply status. The base curve
            is calibrated so an 8-week lead time gives 50%.
          </p>
          <p>
            <code className="bg-gray-100 px-1 rounded text-[11px]">
              base = 1 ÷ (1 + lead_time_weeks ÷ 8)
            </code>
          </p>
          <Defs items={[
            { term: "0 wk (in stock)", def: "100%" },
            { term: "4 wk", def: "67%" },
            { term: "8 wk (baseline)", def: "50%" },
            { term: "16 wk", def: "33%" },
            { term: "24 wk", def: "25%" },
            { term: "36 wk", def: "18%" },
            { term: "52 wk", def: "13%" },
          ]} />
          <p>Status multiplier on top:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>available</strong> — × 1.2 (capped at 100%)</li>
            <li><strong>constrained</strong> — × 1.0 (baseline)</li>
            <li><strong>announced</strong> — × 0.5 (heavy penalty — you can't actually buy it yet)</li>
          </ul>
        </Section>

        {/* Constraints */}
        <Section id="constraints" title="Constraints">
          <p>
            Constraints are dealbreakers, not preferences. There are six.
          </p>
          <h3 className="text-sm font-semibold text-gray-900 mt-3">User-set hard limits</h3>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Max budget ($)</strong> — TCO ceiling in USD. Penalty scales with overshoot ratio.</li>
            <li><strong>Max power per rack (kW)</strong> — flat 30% penalty if exceeded.</li>
            <li><strong>Max lead time (weeks)</strong> — flat 30% penalty if exceeded.</li>
          </ul>
          <h3 className="text-sm font-semibold text-gray-900 mt-3">Derived constraints</h3>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Cooling</strong> — air-cooled site filters out DLC-mandatory GPUs (B300, GB200 NVL72, GB300 NVL72) entirely.</li>
            <li><strong>Workload</strong> — RTX PRO 6000 BSE is inference-only; training/fine-tuning workloads exclude it.</li>
            <li><strong>Model size</strong> — 200B+ models exclude the 96 GB RTX PRO 6000 BSE because the model literally won't fit.</li>
          </ul>
          <p>
            Each violation produces a stable code (<code className="bg-gray-100 px-1 rounded text-[11px]">BUDGET_EXCEEDED</code>, <code className="bg-gray-100 px-1 rounded text-[11px]">DLC_REQUIRED</code>, <code className="bg-gray-100 px-1 rounded text-[11px]">MODEL_TOO_LARGE</code>, etc.) that the API returns alongside the human-readable warning.
          </p>
        </Section>

        {/* Weights */}
        <Section id="weights" title="Weights & sweet-spot ranking">
          <p>
            Every GPU is scored on four axes: <strong>performance</strong>,
            <strong> cost</strong>, <strong>complexity</strong>, and{" "}
            <strong>availability</strong>. To avoid one outlier (a $4M NVL72 rack)
            crushing the cost axis, raw values are <em>rank-normalised</em> across
            the candidate set: best gets 1.0, worst gets 0.0.
          </p>
          <p>
            <code className="bg-gray-100 px-1 rounded text-[11px]">
              composite = w_perf×perf + w_cost×cost + w_cx×cx + w_av×avail
            </code>
            — minus any constraint penalties.
          </p>
          <p>
            The <strong>sweet spot</strong> is the highest-scoring GPU that
            survives every hard rule. If nothing passes, the engine falls back
            to the overall top scorer and surfaces the violations.
          </p>
          <p>
            The default weights (35/30/15/20) target a generic enterprise
            buyer. Slide cost to 100% and you'll get the cheapest option that
            fits; slide performance to 100% and you'll get the fastest one
            regardless of price.
          </p>
        </Section>

        {/* Caveats */}
        <Section id="caveats" title="Caveats & known limits">
          <ul className="list-disc pl-5 space-y-2">
            <li>
              <strong>Decode KV-read</strong> term assumes the full KV cache
              is read each token (matches a non-quantised KV at FP16/BF16).
              Real systems often use FP8 KV (halves the cost) or paged
              attention with eviction (further reduces it for partial-context
              decodes).
            </li>
            <li>
              <strong>Prefill attention</strong> term uses 2 × num_layers
              × hidden_dim × L per token (correct for full standard attention).
              FlashAttention-3 / sliding-window / sparse attention variants
              run cheaper than this — predictions are conservative for those.
            </li>
            <li>
              <strong>OpEx still omits</strong> bandwidth / network egress
              (highly variable; typically &lt;$500/GPU/yr for training, much higher
              for inference serving public traffic), MLOps / sysadmin headcount
              (~1 FTE per 500-1000 GPUs at $120-180k loaded), insurance
              (~0.3-0.5% of asset value/yr), and discretionary tooling like
              Run.AI / Weights & Biases / observability stack ($200-1k/GPU/yr).
            </li>
            <li>
              <strong>Pre-GA SKUs</strong> (B300, GB300, MI350X, MI355X) use
              vendor projections, not measured benchmarks. Treat with
              appropriate scepticism.
            </li>
            <li>
              <strong>Calibration reference</strong> is Llama-3-70B FP16. Other
              architectures (Mixtral, DeepSeek-V3, Gemma) approximate by scaling
              from the closest size; very different shapes will be less accurate.
            </li>
          </ul>
        </Section>

        <footer className="border-t border-gray-200 pt-6 mt-8">
          <Link href="/" className="text-xs text-blue-600 hover:underline">
            ← Back to dashboard
          </Link>
        </footer>
      </article>
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card id={id} className="scroll-mt-20">
      <CardHeader>
        <CardTitle>
          <a href={`#${id}`} className="hover:underline">
            {title}
          </a>
        </CardTitle>
      </CardHeader>
      <CardContent className="prose prose-sm max-w-none text-gray-700 space-y-3 [&_p]:text-sm [&_li]:text-sm">
        {children}
      </CardContent>
    </Card>
  );
}

function Defs({ items }: { items: { term: string; def: string }[] }) {
  return (
    <dl className="space-y-2 my-2">
      {items.map((it) => (
        <div key={it.term} className="grid grid-cols-[180px_1fr] gap-3 text-sm">
          <dt className="font-medium text-gray-900">{it.term}</dt>
          <dd className="text-gray-600">{it.def}</dd>
        </div>
      ))}
    </dl>
  );
}
