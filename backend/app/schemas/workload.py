from pydantic import BaseModel, Field


class WorkloadInput(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_params_b: float = Field(..., description="Model parameters in billions")
    precision: str = Field("FP16", description="FP4, FP8, FP16, BF16, FP32")
    context_length: int = Field(4096, description="Context length in tokens")
    concurrent_users: int = Field(1, description="Number of concurrent users/requests")
    workload_type: str = Field("inference", description="inference, training, quant, risk, hpc, trading")
    batch_size: int = Field(1, description="Batch size")
    finance_benchmark_category: str | None = Field(
        None, description="Optional: quant, risk, inference, hpc, trading, tokenization"
    )


class ConstraintInput(BaseModel):
    max_budget_gbp: float | None = Field(None, description="Maximum budget in GBP")
    max_power_per_rack_kw: float | None = Field(None, description="Max power per rack in kW")
    cooling_type: str = Field("air", description="air or liquid")
    max_lead_time_weeks: int | None = Field(None, description="Max acceptable lead time in weeks")
    metric_weights: dict[str, float] = Field(
        default={"performance": 0.35, "cost": 0.30, "complexity": 0.15, "availability": 0.20},
        description="Weights for each metric (should sum to 1.0)",
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
    kv_cache_gb: float | None = None
    max_context_length: int | None = None
    tco_gbp: float | None = None
    capex_gbp: float | None = None
    opex_monthly_gbp: float | None = None
    tokens_per_gbp: float | None = None
    complexity_score: float | None = None
    availability_score: float | None = None
    composite_score: float | None = None
    topology: TopologyResult | None = None
    rack_plan: RackPlanResult | None = None
    benchmark_scores: dict[str, float] | None = None
    warnings: list[str] = []


class ComparisonResponse(BaseModel):
    workload: WorkloadInput
    constraints: ConstraintInput
    results: list[GPUResult]
    sweet_spot_gpu: str | None = None
