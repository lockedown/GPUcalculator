"""Availability scoring engine — lead time & supply chain weighting."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import GPU, Availability

BASELINE_WEEKS = 8  # Reference lead time for scoring


@dataclass
class AvailabilityResult:
    lead_time_weeks: int
    supply_status: str
    score: float  # 0-1, higher = more available
    meets_constraint: bool


def calc_availability(
    db: Session,
    gpu: GPU,
    max_lead_time_weeks: int | None = None,
) -> AvailabilityResult:
    """
    Calculate availability score.
    Formula: 1.0 / (1 + lead_time_weeks / baseline_weeks)
    """
    avail = db.query(Availability).filter(Availability.gpu_id == gpu.id).first()

    if not avail:
        # Default for unknown availability
        lead_time = 20
        status = "constrained"
    else:
        lead_time = avail.lead_time_weeks
        status = avail.supply_status

    # Score: higher = better availability
    score = 1.0 / (1.0 + lead_time / BASELINE_WEEKS)

    # Boost for "available" status
    if status == "available":
        score = min(1.0, score * 1.2)
    elif status == "announced":
        score *= 0.5  # Heavily penalize pre-announcement GPUs

    meets = True
    if max_lead_time_weeks is not None:
        meets = lead_time <= max_lead_time_weeks

    return AvailabilityResult(
        lead_time_weeks=lead_time,
        supply_status=status,
        score=round(score, 4),
        meets_constraint=meets,
    )
