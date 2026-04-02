from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import create_tables
from app.api.routes import hardware, benchmarks, calculate, compare, networking, prices, export

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
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
app.include_router(export.router, prefix=settings.API_V1_PREFIX, tags=["export"])


@app.on_event("startup")
async def startup():
    create_tables()


@app.get("/health")
async def health():
    return {"status": "ok"}
