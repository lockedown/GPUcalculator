from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    gpu_id = Column(Integer, ForeignKey("gpus.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    price_usd = Column(Float, nullable=False)
    source = Column(String(50), default="estimate")  # estimate, msrp, market, reseller

    gpu = relationship("GPU", backref="price_history")
