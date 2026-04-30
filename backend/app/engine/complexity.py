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
    """Calculate complexity score. Higher = easier to deploy.

    Base: software stack maturity (1-10 from the SoftwareStack table)
    Penalties:
      - FP8 requested but stack has limited/no support: +1 (partial) or +2 (none)
      - Rack-scale deployment (NVL72): +2 (specialised facility & ops)

    Cooling mismatches (air site + liquid GPU) are NOT penalised here — they
    are handled by the optimizer's structured constraint codes
    (``Violation.COOLING_HARD`` / ``COOLING_SOFT`` / ``DLC_REQUIRED``) so they
    only apply once. ``user_cooling`` is kept in the signature for backward
    compatibility but no longer affects the score.
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
    breakdown: dict[str, float] = {}

    # FP8 stack-maturity penalty
    if precision == "FP8":
        fp8_level = stack.fp8_support_level if stack else "none"
        if fp8_level == "none":
            penalties += 2.0
            breakdown["no_fp8_support"] = 2.0
        elif fp8_level == "partial":
            penalties += 1.0
            breakdown["partial_fp8_support"] = 1.0

    # Rack-scale operational penalty (specialised power/cooling/handling)
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
