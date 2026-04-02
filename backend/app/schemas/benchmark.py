from pydantic import BaseModel


class BenchmarkBase(BaseModel):
    benchmark_name: str
    workload_category: str
    workload_description: str | None = None
    rating: str | None = None
    bar_pct: float | None = None
    metric_value: str | None = None
    metric_numeric: float | None = None
    metric_unit: str | None = None


class BenchmarkRead(BenchmarkBase):
    id: int
    gpu_id: int

    class Config:
        from_attributes = True


class BenchmarkWithGPU(BenchmarkRead):
    gpu_name: str | None = None
    gpu_vendor: str | None = None
