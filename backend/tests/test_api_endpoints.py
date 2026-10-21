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

    def test_db_down_is_503_and_does_not_leak(self, client, monkeypatch):
        class _Down:
            def execute(self, *_):
                raise RuntimeError("connection to ep-secret-host failed")

            def close(self):
                pass

        monkeypatch.setattr("app.db.database.SessionLocal", _Down)
        r = client.get("/health")
        assert r.status_code == 503
        assert "ep-secret-host" not in r.text


class TestHardwareEndpoints:
    def test_list_all(self, client):
        r = client.get("/api/hardware")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 14  # 8 from HTML + H100 SXM5, RTX PRO 6000 BSE, Vera Rubin NVL72, Rubin CPX, MI450X, MI455X

    def test_filter_nvidia(self, client):
        r = client.get("/api/hardware?vendor=NVIDIA")
        assert r.status_code == 200
        data = r.json()
        assert all(g["vendor"] == "NVIDIA" for g in data)
        assert len(data) == 9  # H100, H200, B200, B300, GB200, GB300, RTX PRO 6000 BSE, Vera Rubin NVL72, Rubin CPX

    def test_filter_amd(self, client):
        r = client.get("/api/hardware?vendor=AMD")
        assert r.status_code == 200
        data = r.json()
        assert all(g["vendor"] == "AMD" for g in data)
        assert len(data) == 5  # MI300X, MI350X, MI355X, MI450X, MI455X

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
        r = client.post("/api/compare", json=self.WORKLOAD)
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "sweet_spot_gpu" in data
        assert len(data["results"]) == 14  # All seeded GPUs (HTML + extras-only)

    def test_results_are_ranked(self, client):
        r = client.post("/api/compare", json=self.WORKLOAD)
        assert r.status_code == 200
        results = r.json()["results"]
        scores = [r["composite_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_fp8_precision(self, client):
        payload = {**self.WORKLOAD["workload"], "precision": "FP8"}
        r = client.post("/api/compare", json={"workload": payload})
        assert r.status_code == 200

    def test_large_model(self, client):
        payload = {**self.WORKLOAD["workload"], "model_params_b": 405}
        r = client.post("/api/compare", json={"workload": payload})
        assert r.status_code == 200
        results = r.json()["results"]
        for res in results:
            if res["topology"]:
                assert res["topology"]["gpu_count"] >= 1


class TestCalculateEndpoint:
    def test_returns_one_result_per_gpu(self, client):
        r = client.post("/api/calculate", json={"workload": {"model_params_b": 70}})
        assert r.status_code == 200
        assert len(r.json()) == 14

    def test_constraints_are_optional_but_applied(self, client):
        body = {
            "workload": {"model_params_b": 70},
            "constraints": {"max_lead_time_weeks": 0},
        }
        r = client.post("/api/calculate", json=body)
        assert r.status_code == 200
        assert any("LEAD_TIME_EXCEEDED" in g["violation_codes"] for g in r.json())


class TestInputValidation:
    """Bad input is a 422, never a 500 or a silently wrong answer."""

    @pytest.mark.parametrize("workload", [
        {"model_params_b": 0},
        {"model_params_b": -70},
        {"model_params_b": 1e300},
        {"model_params_b": 70, "concurrent_users": 0},
        {"model_params_b": 70, "concurrent_users": -5},
        {"model_params_b": 70, "context_length": 0},
        {"model_params_b": 70, "precision": "INT8"},
        {"model_params_b": 70, "workload_type": "gaming"},
        {"model_params_b": 70, "is_moe": True, "num_experts": 8, "active_experts": 0},
        {"model_params_b": 70, "is_moe": True, "num_experts": 8, "active_experts": 9},
    ])
    def test_bad_workload(self, client, workload):
        assert client.post("/api/compare", json={"workload": workload}).status_code == 422

    @pytest.mark.parametrize("constraints", [
        {"amortization_months": 0},
        {"cooling_type": "immersion"},
        {"metric_weights": {"performance": -1.0}},
        {"metric_weights": {"speed": 1.0}},
        {"max_budget_usd": -1},
    ])
    def test_bad_constraints(self, client, constraints):
        body = {"workload": {"model_params_b": 70}, "constraints": constraints}
        assert client.post("/api/compare", json=body).status_code == 422


class TestNetworkingEndpoint:
    def test_list(self, client):
        r = client.get("/api/networking")
        assert r.status_code == 200
        assert len(r.json()) >= 10
