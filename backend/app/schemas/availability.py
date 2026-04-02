from pydantic import BaseModel


class AvailabilityBase(BaseModel):
    lead_time_weeks: int
    supply_status: str


class AvailabilityRead(AvailabilityBase):
    id: int
    gpu_id: int

    class Config:
        from_attributes = True
