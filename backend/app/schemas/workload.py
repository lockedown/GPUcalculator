from pydantic import BaseModel, Field


class WorkloadInput(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_params_b: float = Field(..., description="Model parameters in billions")
    precision: str = Field("FP16", description="FP4, FP8, FP16, BF16, FP32")
    context_length: int = Field(4096, description="Context length in tokens")
    concurrent_users: int = Field(1, description="Number of concurrent users/requests")
    workload_type: str = Field("inference", description="inference, training, pre-training, fine-tuning, quant, risk, hpc, trading")
    batch_size: int = Field(1, description="Batch size")
    is_moe: bool = Field(False, description="Whether the model uses Mixture-of-Experts")
    num_experts: int = Field(8, description="Total number of experts (MoE only)")
    active_experts: int = Field(2, description="Number of active experts per token (MoE only)")
    finance_benchmark_category: str | None = Field(
        None, description="Optional: quant, risk, inference, hpc, trading, tokenization"
    )
    # ---- Multi-tenancy / fractional GPU (Run:ai-style) ----
    multi_tenancy_mode: str = Field(
        "dedicated",
        description=(
            "GPU partitioning mode. 'dedicated' = one workload owns the GPU. "
            "'mig' = NVIDIA MIG hardware partition (Hopper only). "
            "'runai_fractional' = software time-sliced (e.g. Run:ai)."
        ),
    )
    mig_profile: str | None = Field(
        None,
        description=(
            "MIG profile when multi_tenancy_mode='mig'. Common values: "
            "'1g.10gb' (7/GPU), '2g.20gb' (3/GPU), '3g.40gb' (2/GPU), "
            "'4g.40gb' (1/GPU), '7g.full' (1/GPU full-GPU MIG)."
        ),
    )
    tenants: int = Field(
        1,
        description=(
            "Number of co-located tenants. Informational under 'dedicated'; "
            "for 'runai_fractional' divides per-GPU throughput by this number "
            "(time-slicing). For 'mig' it's overridden by the profile's "
            "instances_per_gpu."
        ),
    )
    # ---- Disaggregated prefill/decode (Dynamo-style) ----
    serving_mode: str = Field(
        "colocated",
        description=(
            "'colocated' = one GPU pool runs both prefill and decode (current "
            "default). 'disaggregated' = roles split into separate pools (Dynamo, "
            "DeepSeek-V3 architecture). v1 is observability-only — sizing is "
            "informational, the recommended split is rendered alongside the "
            "topology but cost / rack are still computed against the unified "
            "gpu_count. Heterogeneous SKUs per role land in v2."
        ),
    )


class ConstraintInput(BaseModel):
    max_budget_usd: float | None = Field(None, description="Maximum amortised TCO budget in USD")
    max_power_per_rack_kw: float | None = Field(None, description="Max power per rack in kW")
    cooling_type: str = Field("air", description="air or liquid")
    max_lead_time_weeks: int | None = Field(None, description="Max acceptable lead time in weeks")
    amortization_months: int = Field(
        48,
        description="GPU CapEx amortisation period in months (36, 48, or 60). Default 48 = 4yr (industry middle ground; AWS uses 60, hyperscalers up to 72).",
    )
    # Run-cost OpEx components (USD). Default to typical US enterprise values;
    # set any to 0.0 to opt out of that line.
    colo_usd_per_kw_per_month: float = Field(
        200.0,
        description="Colocation rent per IT-kW per month, USD. CBRE H2 2025: ~$195. Set 0 if self-operated.",
    )
    hw_support_pct_of_capex_per_year: float = Field(
        0.10,
        description="Hardware support contract as fraction of CapEx per year. Typical 8-15% for AI hardware.",
    )
    software_usd_per_gpu_per_year: float = Field(
        1000.0,
        description="Software licensing per GPU per year, USD (e.g. NVIDIA AI Enterprise list ~$1000/GPU/yr).",
    )
    metric_weights: dict[str, float] = Field(
        default={"performance": 0.35, "cost": 0.30, "complexity": 0.15, "availability": 0.20},
        description="Weights for each metric (should sum to 1.0)",
    )
    target_tpot_ms: int | None = Field(
        None,
        description=(
            "Optional target time-per-output-token in ms. Candidates whose "
            "per-user TPOT exceeds this raise the TPOT_MISSED advisory; "
            "purely informational, does not block ranking."
        ),
    )


class TopologyResult(BaseModel):
    gpu_count: int
    nodes: int
    gpus_per_node: int
    parallelism_strategy: str  # "TP only", "TP + PP", "TP + PP + DP"
    tp_degree: int
    pp_degree: int
    dp_degree: int = 1
    effective_bandwidth_gb_s: float | None = None
    cross_node_latency_penalty: float = 0.0
    # Disaggregated prefill/decode view (Sprint 10 — observability v1).
    # In 'colocated' mode prefill_gpu_count == decode_gpu_count == gpu_count
    # and the role strategies mirror parallelism_strategy. In 'disaggregated'
    # mode the engine surfaces a recommended 30/70 prefill/decode split as a
    # hint; cost + rack are still computed against the unified gpu_count.
    serving_mode: str = "colocated"
    prefill_gpu_count: int | None = None
    decode_gpu_count: int | None = None
    prefill_role_strategy: str | None = None
    decode_role_strategy: str | None = None


class RackPlanResult(BaseModel):
    total_racks: int
    servers_per_rack: int
    gpus_per_rack: int
    u_per_server: int
    u_utilization_pct: float
    power_per_gpu_kw: float
    power_per_server_kw: float
    power_per_rack_kw: float
    total_power_kw: float
    pue_adjusted_power_kw: float
    pdu_tier: str
    pdu_tier_label: str
    pdu_headroom_pct: float
    cooling_type: str
    cooling_capacity_kw: float
    cooling_headroom_pct: float
    fits_power_constraint: bool
    fits_cooling: bool
    density_warning: str | None = None


class GPUResult(BaseModel):
    gpu_id: int
    gpu_name: str
    gpu_vendor: str
    tokens_per_sec: float | None = None
    prefill_tokens_per_sec: float | None = None
    decode_tokens_per_sec: float | None = None
    # Per-user latency view — what one user actually experiences at the
    # configured concurrency. ttft_ms = context_length / per_user_prefill_tps;
    # tpot_ms = 1000 / per_user_decode_tps. Both are derived (no extra cost).
    ttft_ms: float | None = None
    tpot_ms: float | None = None
    per_user_decode_tps: float | None = None
    # Multi-tenancy view — populated only when multi_tenancy_mode != "dedicated".
    # tenancy_mode_applied echoes the mode actually applied (may differ from
    # request if hard-gated, e.g. MIG on Blackwell falls back to dedicated with
    # MIG_NOT_SUPPORTED in violation_codes).
    tenancy_mode_applied: str | None = None
    tenants_per_gpu: int | None = None
    per_tenant_decode_tps: float | None = None
    per_tenant_kv_cache_gb: float | None = None
    # MoE-specific surfacing — populated only when workload.is_moe.
    # active_param_fraction = active_experts / num_experts; effective_bw_per_token
    # is the active-expert weight bytes streamed per output token (the
    # bandwidth-bound denominator visible to the customer);
    # routing_overhead_pct is the all-to-all dispatch/combine penalty that's
    # already baked into decode_tokens_per_sec (negative number — surfaced for
    # transparency).
    moe_active_param_fraction: float | None = None
    moe_effective_bw_per_token_gb: float | None = None
    moe_routing_overhead_pct: float | None = None
    kv_cache_gb: float | None = None
    max_context_length: int | None = None
    tco_usd: float | None = None
    capex_usd: float | None = None
    opex_monthly_usd: float | None = None
    # Itemised monthly OpEx: keys are power_usd, colocation_usd,
    # hw_support_usd, software_usd. None when calc skipped.
    opex_breakdown: dict[str, float] | None = None
    tokens_per_usd: float | None = None
    complexity_score: float | None = None
    availability_score: float | None = None
    composite_score: float | None = None
    topology: TopologyResult | None = None
    rack_plan: RackPlanResult | None = None
    benchmark_scores: dict[str, float] | None = None
    is_estimated: bool = False
    warnings: list[str] = []
    # Stable machine-readable codes for constraint violations / advisories.
    # Used by sweet-spot filtering and penalty calculation; safe for the
    # frontend to drive icons / filter chips off of.
    violation_codes: list[str] = []


class ComparisonResponse(BaseModel):
    workload: WorkloadInput
    constraints: ConstraintInput
    results: list[GPUResult]
    sweet_spot_gpu: str | None = None
