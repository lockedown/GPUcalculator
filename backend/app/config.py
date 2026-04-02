import os
from pathlib import Path
from pydantic_settings import BaseSettings


def _parse_cors() -> list[str]:
    """Parse CORS_ORIGINS from env (comma-separated) or use local defaults."""
    raw = os.getenv("CORS_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


class Settings(BaseSettings):
    PROJECT_NAME: str = "GPU Deployment Optimizer"
    API_V1_PREFIX: str = "/api"
    DATABASE_URL: str = "sqlite:///./gpu_optimizer.db"
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    BENCHMARK_HTML_PATH: str = str(
        Path(__file__).resolve().parent.parent.parent / "Finance GPU Benchmark Matrix.html"
    )
    CORS_ORIGINS: list[str] = _parse_cors()

    class Config:
        env_file = ".env"


settings = Settings()
