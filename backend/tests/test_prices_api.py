"""Tests for the price history and export API endpoints."""

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

    def test_h200_price_trend_declining(self):
        """H200 should show a declining price trend over time."""
        r = client.get("/api/prices")
        h200 = next(g for g in r.json() if g["gpu_name"] == "H200 SXM")
        prices = [p["price_usd"] for p in h200["prices"]]
        assert len(prices) >= 3
        assert prices[-1] < prices[0], "H200 price should decline over time"


class TestExportEndpoint:
    """Test POST /api/export/csv and /api/export/json."""

    WORKLOAD = {
        "model_params_b": 70,
        "precision": "FP16",
        "context_length": 4096,
        "concurrent_users": 1,
        "workload_type": "inference",
        "batch_size": 1,
    }

    def test_export_csv_returns_200(self):
        r = client.post("/api/export/csv", json=self.WORKLOAD)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_export_csv_has_header_row(self):
        r = client.post("/api/export/csv", json=self.WORKLOAD)
        lines = r.text.strip().split("\n")
        assert len(lines) >= 2  # Header + at least 1 data row
        header = lines[0]
        assert "Rank" in header
        assert "GPU" in header
        assert "Score" in header
        assert "TCO" in header

    def test_export_csv_has_all_gpus(self):
        r = client.post("/api/export/csv", json=self.WORKLOAD)
        lines = r.text.strip().split("\n")
        # Header + 10 GPUs (8 from HTML + H100 SXM5 + RTX PRO 6000 BSE)
        assert len(lines) == 11

    def test_export_csv_includes_rack_data(self):
        r = client.post("/api/export/csv", json=self.WORKLOAD)
        header = r.text.strip().split("\n")[0]
        assert "Racks" in header
        assert "Power/Rack" in header
        assert "PDU Tier" in header

    def test_export_json_returns_200(self):
        r = client.post("/api/export/json", json=self.WORKLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "generated_at" in data
        assert "workload" in data
        assert "results" in data
        assert "sweet_spot_gpu" in data

    def test_export_json_results_have_rack_plan(self):
        r = client.post("/api/export/json", json=self.WORKLOAD)
        results = r.json()["results"]
        # GPUs filtered by constraints (e.g. DLC-only) may have rack_plan=None
        evaluated = [res for res in results if res.get("tokens_per_sec") is not None]
        assert len(evaluated) > 0
        for result in evaluated:
            assert "rack_plan" in result
            rack = result["rack_plan"]
            assert rack is not None
            assert "total_racks" in rack
            assert "power_per_rack_kw" in rack
            assert "pdu_tier_label" in rack

    def test_export_json_ranked(self):
        r = client.post("/api/export/json", json=self.WORKLOAD)
        results = r.json()["results"]
        scores = [r["composite_score"] for r in results if r["composite_score"]]
        assert scores == sorted(scores, reverse=True)
