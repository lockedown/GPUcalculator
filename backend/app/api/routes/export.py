"""Export comparison results as CSV or JSON report."""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.workload import WorkloadInput, ConstraintInput
from app.engine.optimizer import run_comparison

router = APIRouter()


class ExportRequest(WorkloadInput):
    """Extends WorkloadInput with optional constraints for export."""
    pass


@router.post("/export/csv")
def export_csv(workload: WorkloadInput, db: Session = Depends(get_db)):
    """Export comparison results as a CSV file."""
    constraints = ConstraintInput()
    comparison = run_comparison(db, workload, constraints)

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header
    writer.writerow([
        "Rank", "GPU", "Vendor", "Score",
        "Decode tok/s", "Prefill tok/s",
        "TCO (GBP)", "CapEx (GBP)", "OpEx/mo (GBP)", "Tokens/GBP/mo",
        "Complexity", "Availability",
        "GPU Count", "Nodes", "Strategy",
        "TP", "PP", "DP",
        "Racks", "Power/Rack (kW)", "Total Power (kW)", "PDU Tier",
        "Warnings",
    ])

    for i, r in enumerate(comparison.results, 1):
        topo = r.topology
        rack = r.rack_plan
        writer.writerow([
            i,
            r.gpu_name,
            r.gpu_vendor,
            f"{r.composite_score:.4f}" if r.composite_score else "",
            f"{r.decode_tokens_per_sec:.0f}" if r.decode_tokens_per_sec else "",
            f"{r.prefill_tokens_per_sec:.0f}" if r.prefill_tokens_per_sec else "",
            f"{r.tco_gbp:.0f}" if r.tco_gbp else "",
            f"{r.capex_gbp:.0f}" if r.capex_gbp else "",
            f"{r.opex_monthly_gbp:.0f}" if r.opex_monthly_gbp else "",
            f"{r.tokens_per_gbp:.0f}" if r.tokens_per_gbp else "",
            f"{r.complexity_score:.2f}" if r.complexity_score else "",
            f"{r.availability_score:.2f}" if r.availability_score else "",
            topo.gpu_count if topo else "",
            topo.nodes if topo else "",
            topo.parallelism_strategy if topo else "",
            topo.tp_degree if topo else "",
            topo.pp_degree if topo else "",
            topo.dp_degree if topo else "",
            rack.total_racks if rack else "",
            rack.power_per_rack_kw if rack else "",
            rack.total_power_kw if rack else "",
            rack.pdu_tier_label if rack else "",
            "; ".join(r.warnings) if r.warnings else "",
        ])

    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gpu_comparison_{timestamp}.csv"

    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export/json")
def export_json(workload: WorkloadInput, db: Session = Depends(get_db)):
    """Export full comparison results as JSON report."""
    constraints = ConstraintInput()
    comparison = run_comparison(db, workload, constraints)

    return {
        "generated_at": datetime.now().isoformat(),
        "workload": comparison.workload.model_dump(),
        "constraints": comparison.constraints.model_dump(),
        "sweet_spot_gpu": comparison.sweet_spot_gpu,
        "results": [r.model_dump() for r in comparison.results],
    }
