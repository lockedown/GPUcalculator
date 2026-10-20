"""Refresh GPU MSRP + grid-pricing data from a known-good-source payload.

This is the v2.3 mechanism asked for in the roadmap (item #11). Designed
to be called three ways:

  1. **Manual** — run locally with a JSON file you've assembled by hand
     from quarterly NVIDIA / AMD pricing notes, UBS / SemiAnalysis channel
     surveys, CBRE colo rates, EPA eGRID grid intensity:

         python -m scripts.update_gpu_prices --input refresh-2026-Q3.json

  2. **Stdin** — pipe in from another script (curl from a SemiAnalysis API,
     a sheet export, etc.):

         curl https://internal/.../refresh.json | python -m scripts.update_gpu_prices

  3. **Future cron** — wrap in a scheduled task (v2.3b roadmap item #9)
     that pulls from each known-good source and writes a single combined
     JSON to feed this script. Same code path either way.

Payload schema:

    {
      "as_of": "2026-08-15",                # date the surveys were taken
      "source": "UBS H2-2026 channel note", # free-form attribution
      "gpus": [
        {"name": "H100 SXM5", "msrp_usd": 32000},
        {"name": "B200 HGX",  "msrp_usd": 38000},
        ...
      ]
    }

For each entry we:
  - UPDATE ``gpus.msrp_usd`` and ``gpus.msrp_as_of``
  - INSERT a row into ``price_history`` with the given source attribution
  - Print a one-line summary per GPU (old → new) so the operator can
    sanity-check before committing

Pass ``--dry-run`` to print the planned changes without touching the DB.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date


# Mirrors PriceHistory.source String(50). Postgres enforces it (SQLite doesn't),
# so check up front rather than failing mid-write against Neon.
MAX_SOURCE_LEN = 50


@dataclass
class GpuPriceUpdate:
    name: str
    msrp_usd: float


@dataclass
class RefreshPayload:
    as_of: str
    source: str
    gpus: list[GpuPriceUpdate]


def parse_payload(raw: dict) -> RefreshPayload:
    """Validate and normalise the input JSON.

    Raises ``ValueError`` with a precise message on malformed input.
    """
    if not isinstance(raw, dict):
        raise ValueError("payload must be a JSON object")

    as_of = raw.get("as_of")
    if not isinstance(as_of, str) or len(as_of) != 10 or as_of[4] != "-" or as_of[7] != "-":
        raise ValueError("'as_of' must be an ISO YYYY-MM-DD date string")

    source = raw.get("source", "manual refresh")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("'source' must be a non-empty string")
    if len(source.strip()) > MAX_SOURCE_LEN:
        raise ValueError(
            f"'source' must be at most {MAX_SOURCE_LEN} characters "
            f"(got {len(source.strip())}); price_history.source is VARCHAR({MAX_SOURCE_LEN})"
        )

    gpus_raw = raw.get("gpus")
    if not isinstance(gpus_raw, list) or not gpus_raw:
        raise ValueError("'gpus' must be a non-empty list of {name, msrp_usd} entries")

    updates: list[GpuPriceUpdate] = []
    for i, entry in enumerate(gpus_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"gpus[{i}] must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"gpus[{i}].name must be a non-empty string")
        msrp = entry.get("msrp_usd")
        if not isinstance(msrp, (int, float)) or msrp <= 0:
            raise ValueError(f"gpus[{i}].msrp_usd must be a positive number")
        updates.append(GpuPriceUpdate(name=name, msrp_usd=float(msrp)))

    return RefreshPayload(as_of=as_of, source=source.strip(), gpus=updates)


def apply_updates(payload: RefreshPayload, *, dry_run: bool) -> int:
    """Apply the price updates against the configured DATABASE_URL.

    Returns the number of GPUs whose MSRP actually changed (skipped rows
    where the new price equals the old price are not counted but are still
    logged with a "no change" note for transparency).
    """
    # Late imports — keep the script importable for unit tests without
    # requiring a DB connection until we actually run.
    from app.db.database import SessionLocal
    from app.models import GPU, PriceHistory

    session = SessionLocal()
    changed = 0
    try:
        for upd in payload.gpus:
            gpu = session.query(GPU).filter(GPU.name == upd.name).one_or_none()
            if gpu is None:
                print(f"  ⚠ {upd.name:20s} — not in catalogue, skipping", file=sys.stderr)
                continue
            old = gpu.msrp_usd
            old_as_of = gpu.msrp_as_of or "(unstamped)"
            if old == upd.msrp_usd and gpu.msrp_as_of == payload.as_of:
                print(f"  · {upd.name:20s} ${old:,.0f} (no change, already at {payload.as_of})")
                continue
            print(
                f"  → {upd.name:20s} "
                f"${old:,.0f} ({old_as_of}) → ${upd.msrp_usd:,.0f} ({payload.as_of}) "
                f"[{payload.source}]"
            )
            if not dry_run:
                gpu.msrp_usd = upd.msrp_usd
                gpu.msrp_as_of = payload.as_of
                # Append a price_history row for the audit trail. Even when
                # only as_of changed (price held flat), we still want a fresh
                # data point so the timeline reflects the verification.
                session.add(
                    PriceHistory(
                        gpu_id=gpu.id,
                        date=date.fromisoformat(payload.as_of),
                        price_usd=upd.msrp_usd,
                        source=payload.source,
                    )
                )
            changed += 1
        if not dry_run:
            session.commit()
    finally:
        session.close()
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--input",
        "-i",
        help="Path to a JSON refresh payload. Reads from stdin if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without touching the database.",
    )
    args = parser.parse_args(argv)

    raw_text = (
        open(args.input, encoding="utf-8").read() if args.input else sys.stdin.read()
    )
    raw = json.loads(raw_text)
    payload = parse_payload(raw)

    print(
        f"Refresh payload: {len(payload.gpus)} GPUs · as_of {payload.as_of} · "
        f"source {payload.source!r}"
    )
    if args.dry_run:
        print("(dry run — no changes will be persisted)")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL must be set", file=sys.stderr)
        return 2

    changed = apply_updates(payload, dry_run=args.dry_run)
    suffix = " (dry run)" if args.dry_run else ""
    print(f"\n{changed} GPU(s) {'would be updated' if args.dry_run else 'updated'}{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
