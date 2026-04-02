from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.workload import WorkloadInput, ConstraintInput, ComparisonResponse
from app.engine.optimizer import run_comparison

router = APIRouter()


@router.post("/compare", response_model=ComparisonResponse)
def compare(
    workload: WorkloadInput,
    constraints: ConstraintInput | None = None,
    db: Session = Depends(get_db),
):
    if constraints is None:
        constraints = ConstraintInput()
    return run_comparison(db, workload, constraints)
