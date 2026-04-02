"""Vercel Python serverless entry point — exposes the FastAPI app."""

import sys
from pathlib import Path

# Add backend/ to Python path so `from app.main import app` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402, F401 — Vercel picks this up as ASGI handler
