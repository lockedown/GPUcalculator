from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import GPU, PriceHistory
from app.schemas.price_history import PriceHistoryRead, PriceHistoryByGPU

router = APIRouter()


@router.get("/prices", response_model=list[PriceHistoryByGPU])
def list_all_prices(db: Session = Depends(get_db)):
    """Get price history for all GPUs."""
    gpus = db.query(GPU).order_by(GPU.vendor, GPU.name).all()
    result = []
    for gpu in gpus:
        prices = (
            db.query(PriceHistory)
            .filter(PriceHistory.gpu_id == gpu.id)
            .order_by(PriceHistory.date)
            .all()
        )
        if prices:
            result.append(PriceHistoryByGPU(
                gpu_id=gpu.id,
                gpu_name=gpu.name,
                prices=[PriceHistoryRead.model_validate(p) for p in prices],
            ))
    return result


@router.get("/prices/{gpu_id}", response_model=PriceHistoryByGPU)
def get_gpu_prices(gpu_id: int, db: Session = Depends(get_db)):
    """Get price history for a specific GPU."""
    gpu = db.query(GPU).filter(GPU.id == gpu_id).first()
    if not gpu:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="GPU not found")
    prices = (
        db.query(PriceHistory)
        .filter(PriceHistory.gpu_id == gpu_id)
        .order_by(PriceHistory.date)
        .all()
    )
    return PriceHistoryByGPU(
        gpu_id=gpu.id,
        gpu_name=gpu.name,
        prices=[PriceHistoryRead.model_validate(p) for p in prices],
    )
