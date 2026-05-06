"""Shared test fixtures — seeds the SQLite test database once per session
and exposes a per-module ``db`` SQLAlchemy session.
"""

import pytest
from app.db.database import SessionLocal, create_tables
from app.db.seed import run_seed


@pytest.fixture(scope="session", autouse=True)
def _seed_test_db():
    """Create tables and seed data before any tests run."""
    run_seed()


@pytest.fixture(scope="module")
def db():
    """Per-module SQLAlchemy session against the seeded test DB."""
    create_tables()
    session = SessionLocal()
    yield session
    session.close()


def mock_gpu(**overrides):
    """Build a duck-typed GPU stand-in for engine unit tests that don't need
    a real DB row. Defaults model an 8-GPU NVLink-5 baseboard; pass overrides
    for the fields that matter to the test under examination.
    """
    defaults = dict(
        name="MockGPU",
        vendor="NVIDIA",
        generation="Blackwell",
        hbm_capacity_gb=192,
        memory_gb=192,
        memory_type="HBM3e",
        memory_bandwidth_tbps=8.0,
        interconnect_type="NVLink 5",
        nvlink_topology="nvswitch",
        cooling_requirement="Any",
        supported_workloads=["inference", "training", "fine-tuning"],
        supports_fp4=True,
        is_rack_scale=False,
        rack_gpu_count=None,
        max_gpus_per_node=8,
        interconnect_bw_gb_s=900,
        rack_fabric_bw_tb_s=None,
    )
    defaults.update(overrides)

    class _MockGPU:
        pass

    gpu = _MockGPU()
    for k, v in defaults.items():
        setattr(gpu, k, v)
    return gpu
