from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)
    gpu_id = Column(Integer, ForeignKey("gpus.id"), nullable=False, unique=True)
    lead_time_weeks = Column(Integer, nullable=False)
    supply_status = Column(String(30), nullable=False)  # available, constrained, announced
    last_updated = Column(DateTime, server_default=func.now())

    gpu = relationship("GPU", back_populates="availability")
