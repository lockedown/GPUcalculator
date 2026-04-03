"""Shared test fixtures — seeds the SQLite test database once per session."""

import pytest
from app.db.database import create_tables
from app.db.seed import run_seed


@pytest.fixture(scope="session", autouse=True)
def _seed_test_db():
    """Create tables and seed data before any tests run."""
    run_seed()
