from pydantic import BaseModel
from datetime import date


class PriceHistoryRead(BaseModel):
    id: int
    gpu_id: int
    date: date
    price_usd: float
    source: str

    class Config:
        from_attributes = True


class PriceHistoryByGPU(BaseModel):
    gpu_id: int
    gpu_name: str
    prices: list[PriceHistoryRead]
