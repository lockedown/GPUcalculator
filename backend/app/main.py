import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.database import create_tables
from app.api.routes import hardware, benchmarks, calculate, compare, networking, prices


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hardware.router, prefix=settings.API_V1_PREFIX, tags=["hardware"])
app.include_router(benchmarks.router, prefix=settings.API_V1_PREFIX, tags=["benchmarks"])
app.include_router(calculate.router, prefix=settings.API_V1_PREFIX, tags=["calculate"])
app.include_router(compare.router, prefix=settings.API_V1_PREFIX, tags=["compare"])
app.include_router(networking.router, prefix=settings.API_V1_PREFIX, tags=["networking"])
app.include_router(prices.router, prefix=settings.API_V1_PREFIX, tags=["prices"])


@app.get("/health")
async def health():
    from sqlalchemy import text
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        # Real error stays in the logs: driver messages can carry host/user.
        logging.getLogger(__name__).exception("health check: database unreachable")
        return JSONResponse({"status": "degraded", "db": "unreachable"}, status_code=503)
    finally:
        db.close()


@app.get(f"{settings.API_V1_PREFIX}/meta")
async def meta():
    """Engine versioning metadata — surfaced on the methodology page so users
    can tell at a glance which calibration anchor and pricing snapshot the
    current results are computed against.
    """
    from app.engine.calibration import CALIBRATION_VERSION
    return {
        "calibration_version": CALIBRATION_VERSION,
        "calibration_basis": "Llama-3-70B FP16 — MLPerf / vLLM / NVIDIA published results",
    }
