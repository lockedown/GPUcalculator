from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Benchmark, GPU
from app.schemas.benchmark import BenchmarkRead, BenchmarkWithGPU

router = APIRouter()


@router.get("/benchmarks", response_model=list[BenchmarkWithGPU])
def list_benchmarks(
    category: str | None = None,
    gpu_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(
        Benchmark,
        GPU.name.label("gpu_name"),
        GPU.vendor.label("gpu_vendor"),
    ).join(GPU)

    if category:
        query = query.filter(Benchmark.workload_category == category)
    if gpu_id:
        query = query.filter(Benchmark.gpu_id == gpu_id)

    rows = query.order_by(Benchmark.workload_category, Benchmark.benchmark_name, GPU.vendor, GPU.name).all()

    results = []
    for bench, gpu_name, gpu_vendor in rows:
        data = BenchmarkWithGPU.model_validate(bench)
        data.gpu_name = gpu_name
        data.gpu_vendor = gpu_vendor
        results.append(data)
    return results


@router.get("/benchmarks/{category}", response_model=list[BenchmarkWithGPU])
def get_benchmarks_by_category(category: str, db: Session = Depends(get_db)):
    return list_benchmarks(category=category, db=db)
