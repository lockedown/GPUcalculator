"""Availability scoring engine — lead time & supply chain weighting."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import GPU, Availability

# Reference lead time for the score curve. Picked at 8 weeks because it
# matches H200's typical 2026 availability and gives a clean 0.5 score.
BASELINE_WEEKS = 8

# Multipliers applied after the base score:
#   - GA-shipping GPUs get a small uplift (rewards proven supply chain)
#   - Pre-GA / announced GPUs are heavily discounted (you can't actually buy them)
#   - "constrained" is the implicit baseline (no multiplier)
STATUS_BOOST_AVAILABLE = 1.2
STATUS_PENALTY_ANNOUNCED = 0.5

# Defaults when no Availability row exists for a GPU
DEFAULT_LEAD_TIME_WEEKS = 20
DEFAULT_SUPPLY_STATUS = "constrained"


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
    """Calculate availability score.

    score = 1 / (1 + lead_time_weeks / BASELINE_WEEKS), then a status
    multiplier is applied. Score saturates at 1.0.
    """
    avail = db.query(Availability).filter(Availability.gpu_id == gpu.id).first()

    if avail:
        lead_time = avail.lead_time_weeks
        status = avail.supply_status
    else:
        lead_time = DEFAULT_LEAD_TIME_WEEKS
        status = DEFAULT_SUPPLY_STATUS

    score = 1.0 / (1.0 + lead_time / BASELINE_WEEKS)

    if status == "available":
        score = min(1.0, score * STATUS_BOOST_AVAILABLE)
    elif status == "announced":
        score *= STATUS_PENALTY_ANNOUNCED

    meets = max_lead_time_weeks is None or lead_time <= max_lead_time_weeks

    return AvailabilityResult(
        lead_time_weeks=lead_time,
        supply_status=status,
        score=round(score, 4),
        meets_constraint=meets,
    )
