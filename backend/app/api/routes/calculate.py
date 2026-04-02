from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.workload import WorkloadInput, ConstraintInput, GPUResult
from app.engine.optimizer import run_calculation

router = APIRouter()


@router.post("/calculate", response_model=list[GPUResult])
def calculate(
    workload: WorkloadInput,
    constraints: ConstraintInput | None = None,
    db: Session = Depends(get_db),
):
    if constraints is None:
        constraints = ConstraintInput()
    return run_calculation(db, workload, constraints)
