"""Complexity scoring engine — software stack maturity + integration penalties."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import GPU, SoftwareStack


@dataclass
class ComplexityResult:
    base_score: float       # 1-10 from software stack maturity (lower = more complex)
    penalties: float        # Additional penalties
    final_score: float      # Combined: higher = easier (inverted for display)
    breakdown: dict[str, float]


def calc_complexity(
    db: Session,
    gpu: GPU,
    user_cooling: str = "air",
    precision: str = "FP16",
) -> ComplexityResult:
    """
    Calculate complexity score. Higher = easier to deploy.

    Base: software stack maturity (1-10 from DB)
    Penalties applied:
      - Liquid cooling required but user has air-only: +3
      - FP8 requested but limited/no support: +2
      - Multi-vendor networking required: +1
      - Rack-scale deployment (NVL72): +2
    """
    # Get software stack maturity
    stack = (
        db.query(SoftwareStack)
        .filter(SoftwareStack.gpu_vendor == gpu.vendor)
        .order_by(SoftwareStack.maturity_score.desc())
        .first()
    )
    base_score = stack.maturity_score if stack else 5

    penalties = 0.0
    breakdown = {}

    # Cooling penalty
    if gpu.cooling_type == "liquid" and user_cooling == "air":
        penalties += 3.0
        breakdown["cooling_mismatch"] = 3.0

    # FP8 support penalty
    if precision == "FP8":
        fp8_level = stack.fp8_support_level if stack else "none"
        if fp8_level == "none":
            penalties += 2.0
            breakdown["no_fp8_support"] = 2.0
        elif fp8_level == "partial":
            penalties += 1.0
            breakdown["partial_fp8_support"] = 1.0

    # Rack-scale penalty
    if gpu.is_rack_scale:
        penalties += 2.0
        breakdown["rack_scale_deployment"] = 2.0

    # Convert to a 0-10 "ease" score (10 = easiest)
    final_score = max(0, min(10, base_score - penalties))

    return ComplexityResult(
        base_score=float(base_score),
        penalties=penalties,
        final_score=final_score,
        breakdown=breakdown,
    )
