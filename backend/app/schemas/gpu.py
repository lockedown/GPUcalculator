from pydantic import BaseModel


class GPUBase(BaseModel):
    name: str
    vendor: str
    generation: str
    form_factor: str
    hbm_capacity_gb: float
    hbm_type: str | None = None
    mem_bandwidth_tb_s: float
    bf16_tflops: float | None = None
    fp64_tflops: float | None = None
    fp8_tflops: float | None = None
    fp4_tflops: float | None = None
    tdp_watts: int | None = None
    cooling_type: str = "air"
    intra_node_interconnect: str | None = None
    interconnect_bw_gb_s: float | None = None
    max_gpus_per_node: int = 8
    is_rack_scale: bool = False
    rack_gpu_count: int | None = None
    rack_fabric_bw_tb_s: float | None = None
    msrp_usd: float | None = None
    is_estimated: bool = False
    release_date: str | None = None
    verdict: str | None = None


class GPURead(GPUBase):
    id: int

    class Config:
        from_attributes = True


class GPUDetail(GPURead):
    benchmarks: list["BenchmarkRead"] = []
    availability: "AvailabilityRead | None" = None

    class Config:
        from_attributes = True


# Forward references resolved after all schemas are defined
from app.schemas.benchmark import BenchmarkRead  # noqa: E402
from app.schemas.availability import AvailabilityRead  # noqa: E402

GPUDetail.model_rebuild()
