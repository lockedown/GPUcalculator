"""Tests for the price history API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestPricesEndpoint:
    """Test GET /api/prices endpoints."""

    def test_list_all_prices(self):
        r = client.get("/api/prices")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for gpu in data:
            assert "gpu_id" in gpu
            assert "gpu_name" in gpu
            assert "prices" in gpu
            assert isinstance(gpu["prices"], list)
            for p in gpu["prices"]:
                assert "date" in p
                assert "price_usd" in p
                assert "source" in p

    def test_list_has_all_seeded_gpus(self):
        r = client.get("/api/prices")
        names = [g["gpu_name"] for g in r.json()]
        assert "H200 SXM" in names
        assert "MI300X" in names

    def test_get_single_gpu_prices(self):
        # First get list to find a GPU ID
        r = client.get("/api/prices")
        first = r.json()[0]
        gpu_id = first["gpu_id"]

        r2 = client.get(f"/api/prices/{gpu_id}")
        assert r2.status_code == 200
        data = r2.json()
        assert data["gpu_id"] == gpu_id
        assert len(data["prices"]) > 0

    def test_get_nonexistent_gpu_404(self):
        r = client.get("/api/prices/99999")
        assert r.status_code == 404

    def test_prices_sorted_by_date(self):
        r = client.get("/api/prices")
        for gpu in r.json():
            dates = [p["date"] for p in gpu["prices"]]
            assert dates == sorted(dates), f"Prices not sorted for {gpu['gpu_name']}"

    def test_h200_price_trend_declining_then_tightening(self):
        """H200 dipped post-launch, then rose again as 2025-2026 supply tightened
        (matches H100's own trend and Aug 2026 market pricing surveys — see
        seed.py PRICE_DATA comments). No longer a monotonic decline."""
        r = client.get("/api/prices")
        h200 = next(g for g in r.json() if g["gpu_name"] == "H200 SXM")
        prices = [p["price_usd"] for p in h200["prices"]]
        assert len(prices) >= 3
        assert prices[1] < prices[0], "H200 price should dip shortly after launch"
        assert prices[-1] > prices[1], "H200 price should recover as 2025-2026 supply tightened"
