from pydantic import BaseModel


class NetworkingRead(BaseModel):
    id: int
    name: str
    type: str
    vendor: str
    generation: str | None = None
    bandwidth_gb_s: float
    latency_us: float | None = None
    is_inter_node: int = 0
    notes: str | None = None

    class Config:
        from_attributes = True
