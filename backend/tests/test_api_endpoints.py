"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import create_tables


@pytest.fixture(scope="module")
def client():
    create_tables()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestHardwareEndpoints:
    def test_list_all(self, client):
        r = client.get("/api/hardware")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 10  # 8 from HTML + H100 SXM5 + RTX PRO 6000 BSE

    def test_filter_nvidia(self, client):
        r = client.get("/api/hardware?vendor=NVIDIA")
        assert r.status_code == 200
        data = r.json()
        assert all(g["vendor"] == "NVIDIA" for g in data)
        assert len(data) == 7  # H100, H200, B200, B300, GB200, GB300, RTX PRO 6000 BSE

    def test_filter_amd(self, client):
        r = client.get("/api/hardware?vendor=AMD")
        assert r.status_code == 200
        data = r.json()
        assert all(g["vendor"] == "AMD" for g in data)
        assert len(data) == 3

    def test_get_single_gpu(self, client):
        r = client.get("/api/hardware")
        gpu_id = r.json()[0]["id"]
        r2 = client.get(f"/api/hardware/{gpu_id}")
        assert r2.status_code == 200
        detail = r2.json()
        assert "benchmarks" in detail
        assert "availability" in detail

    def test_get_nonexistent_gpu(self, client):
        r = client.get("/api/hardware/99999")
        assert r.status_code == 404


class TestBenchmarkEndpoints:
    def test_list_all(self, client):
        r = client.get("/api/benchmarks")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 100  # 21 benchmarks × 9+ GPUs

    def test_filter_by_category(self, client):
        r = client.get("/api/benchmarks?category=tokenization")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert all(b["workload_category"] == "tokenization" for b in data)

    def test_category_route(self, client):
        r = client.get("/api/benchmarks/quant")
        assert r.status_code == 200


class TestCompareEndpoint:
    WORKLOAD = {
        "workload": {
            "model_params_b": 70,
            "precision": "FP16",
            "context_length": 4096,
            "concurrent_users": 1,
            "workload_type": "inference",
            "batch_size": 1,
        }
    }

    def test_basic_comparison(self, client):
        r = client.post("/api/compare", json=self.WORKLOAD["workload"])
        if r.status_code == 422:
            # Try nested format
            r = client.post("/api/compare", json=self.WORKLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "sweet_spot_gpu" in data
        assert len(data["results"]) == 10  # All seeded GPUs (HTML + extras-only)

    def test_results_are_ranked(self, client):
        r = client.post("/api/compare", json=self.WORKLOAD["workload"])
        if r.status_code == 422:
            r = client.post("/api/compare", json=self.WORKLOAD)
        assert r.status_code == 200
        results = r.json()["results"]
        scores = [r["composite_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_fp8_precision(self, client):
        payload = {**self.WORKLOAD["workload"], "precision": "FP8"}
        r = client.post("/api/compare", json=payload)
        if r.status_code == 422:
            r = client.post("/api/compare", json={"workload": payload})
        assert r.status_code == 200

    def test_large_model(self, client):
        payload = {**self.WORKLOAD["workload"], "model_params_b": 405}
        r = client.post("/api/compare", json=payload)
        if r.status_code == 422:
            r = client.post("/api/compare", json={"workload": payload})
        assert r.status_code == 200
        results = r.json()["results"]
        for res in results:
            if res["topology"]:
                assert res["topology"]["gpu_count"] >= 1


class TestNetworkingEndpoint:
    def test_list(self, client):
        r = client.get("/api/networking")
        assert r.status_code == 200
        assert len(r.json()) >= 10
