"""Tests for the v2.3 price-refresh script (``scripts/update_gpu_prices.py``).

The script accepts a JSON payload of the shape

    {"as_of": "YYYY-MM-DD", "source": "...", "gpus": [{"name": ..., "msrp_usd": ...}]}

and applies it as a batch of UPDATEs + price_history inserts. We test:

  - ``parse_payload`` validates the payload shape strictly (catches typos
    in source files before they hit the DB)
  - ``apply_updates`` actually writes both the GPU row and the price_history
    audit trail
  - dry-run mode leaves the DB untouched
"""

import pytest

from app.models import GPU, PriceHistory
from scripts.update_gpu_prices import (
    GpuPriceUpdate,
    RefreshPayload,
    apply_updates,
    parse_payload,
)


class TestParsePayload:
    def test_minimal_valid_payload(self):
        p = parse_payload({
            "as_of": "2026-08-15",
            "source": "test",
            "gpus": [{"name": "H100 SXM5", "msrp_usd": 32000}],
        })
        assert p.as_of == "2026-08-15"
        assert p.source == "test"
        assert p.gpus == [GpuPriceUpdate(name="H100 SXM5", msrp_usd=32000.0)]

    def test_default_source_when_omitted(self):
        p = parse_payload({
            "as_of": "2026-08-15",
            "gpus": [{"name": "MI300X", "msrp_usd": 21000}],
        })
        assert p.source == "manual refresh"

    def test_rejects_source_longer_than_column(self):
        with pytest.raises(ValueError, match="at most 50 characters"):
            parse_payload({
                "as_of": "2026-08-15",
                "source": "x" * 51,
                "gpus": [{"name": "MI300X", "msrp_usd": 21000}],
            })

    def test_accepts_source_at_column_limit(self):
        p = parse_payload({
            "as_of": "2026-08-15",
            "source": "x" * 50,
            "gpus": [{"name": "MI300X", "msrp_usd": 21000}],
        })
        assert len(p.source) == 50

    def test_rejects_non_dict_root(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_payload([])  # type: ignore[arg-type]

    def test_rejects_missing_as_of(self):
        with pytest.raises(ValueError, match="as_of"):
            parse_payload({"source": "x", "gpus": [{"name": "H100 SXM5", "msrp_usd": 1}]})

    def test_rejects_malformed_as_of(self):
        with pytest.raises(ValueError, match="as_of"):
            parse_payload({"as_of": "2026/08/15", "source": "x", "gpus": [{"name": "h", "msrp_usd": 1}]})
        with pytest.raises(ValueError, match="as_of"):
            parse_payload({"as_of": "Aug 15 2026", "source": "x", "gpus": [{"name": "h", "msrp_usd": 1}]})

    def test_rejects_empty_gpus(self):
        with pytest.raises(ValueError, match="non-empty list"):
            parse_payload({"as_of": "2026-08-15", "source": "x", "gpus": []})

    def test_rejects_non_positive_price(self):
        with pytest.raises(ValueError, match="msrp_usd"):
            parse_payload({
                "as_of": "2026-08-15",
                "gpus": [{"name": "H100 SXM5", "msrp_usd": 0}],
            })
        with pytest.raises(ValueError, match="msrp_usd"):
            parse_payload({
                "as_of": "2026-08-15",
                "gpus": [{"name": "H100 SXM5", "msrp_usd": -1}],
            })

    def test_rejects_missing_name(self):
        with pytest.raises(ValueError, match="name"):
            parse_payload({"as_of": "2026-08-15", "gpus": [{"msrp_usd": 30000}]})


class TestApplyUpdates:
    def test_dry_run_does_not_persist(self, db):
        before = db.query(GPU).filter(GPU.name == "H100 SXM5").one().msrp_usd
        payload = RefreshPayload(
            as_of="2099-12-31",
            source="dry-run test",
            gpus=[GpuPriceUpdate(name="H100 SXM5", msrp_usd=999_999.0)],
        )
        apply_updates(payload, dry_run=True)
        # Refresh from DB
        after = db.query(GPU).filter(GPU.name == "H100 SXM5").one().msrp_usd
        assert after == before, "dry-run must not mutate the GPU row"

    def test_unknown_gpu_skipped_silently(self, db):
        payload = RefreshPayload(
            as_of="2026-08-15",
            source="test",
            gpus=[GpuPriceUpdate(name="FakeGPU 9000", msrp_usd=1.0)],
        )
        # Should not raise, just print a warning to stderr.
        changed = apply_updates(payload, dry_run=True)
        assert changed == 0

    def test_writes_price_history_on_change(self, db):
        # Snapshot the count before
        h100 = db.query(GPU).filter(GPU.name == "H100 SXM5").one()
        before_count = (
            db.query(PriceHistory).filter(PriceHistory.gpu_id == h100.id).count()
        )

        payload = RefreshPayload(
            as_of="2099-01-01",
            source="test_writes_price_history_on_change",
            gpus=[GpuPriceUpdate(name="H100 SXM5", msrp_usd=99_999.0)],
        )
        changed = apply_updates(payload, dry_run=False)
        assert changed == 1

        db.expire_all()  # force re-read after cross-session commit
        h100_after = db.query(GPU).filter(GPU.name == "H100 SXM5").one()
        assert h100_after.msrp_usd == 99_999.0
        assert h100_after.msrp_as_of == "2099-01-01"
        after_count = (
            db.query(PriceHistory).filter(PriceHistory.gpu_id == h100.id).count()
        )
        assert after_count == before_count + 1

        # Restore so this test doesn't pollute the shared session-scoped DB.
        h100_after.msrp_usd = 30000.0
        h100_after.msrp_as_of = "2026-04-01"
        db.commit()

    def test_no_change_when_already_at_target(self, db):
        h100 = db.query(GPU).filter(GPU.name == "H100 SXM5").one()
        # Apply the current values back at us — should be a no-op.
        payload = RefreshPayload(
            as_of=h100.msrp_as_of,
            source="no-op",
            gpus=[GpuPriceUpdate(name="H100 SXM5", msrp_usd=h100.msrp_usd)],
        )
        before_history = (
            db.query(PriceHistory).filter(PriceHistory.gpu_id == h100.id).count()
        )
        changed = apply_updates(payload, dry_run=False)
        after_history = (
            db.query(PriceHistory).filter(PriceHistory.gpu_id == h100.id).count()
        )
        assert changed == 0
        assert after_history == before_history, "no-op must not append to price_history"
