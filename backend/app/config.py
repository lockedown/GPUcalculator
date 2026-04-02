from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "GPU Deployment Optimizer"
    API_V1_PREFIX: str = "/api"
    DATABASE_URL: str = "sqlite:///./gpu_optimizer.db"
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    BENCHMARK_HTML_PATH: str = str(
        Path(__file__).resolve().parent.parent.parent / "Finance GPU Benchmark Matrix.html"
    )
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
