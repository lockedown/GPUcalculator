from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models import GPU
from app.schemas.gpu import GPURead, GPUDetail

router = APIRouter()


@router.get("/hardware", response_model=list[GPURead])
def list_gpus(vendor: str | None = None, db: Session = Depends(get_db)):
    query = db.query(GPU)
    if vendor:
        query = query.filter(GPU.vendor.ilike(vendor))
    return query.order_by(GPU.vendor, GPU.name).all()


@router.get("/hardware/{gpu_id}", response_model=GPUDetail)
def get_gpu(gpu_id: int, db: Session = Depends(get_db)):
    gpu = (
        db.query(GPU)
        .options(joinedload(GPU.benchmarks), joinedload(GPU.availability))
        .filter(GPU.id == gpu_id)
        .first()
    )
    if not gpu:
        raise HTTPException(status_code=404, detail="GPU not found")
    return gpu
