from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    gpu_id = Column(Integer, ForeignKey("gpus.id"), nullable=False, index=True)

    benchmark_name = Column(String(100), nullable=False)
    workload_category = Column(String(30), nullable=False, index=True)  # quant, risk, inference, hpc, trading, tokenization
    workload_description = Column(Text)

    # Score data (from HTML)
    rating = Column(String(20))  # Baseline, Limited, Capable, Strong, Best, Best+, N/A
    bar_pct = Column(Float)  # 0-100 bar width percentage
    metric_value = Column(String(100))  # Raw text e.g. "~45K tok/s"
    metric_numeric = Column(Float)  # Parsed numeric value where possible
    metric_unit = Column(String(50))  # tok/s, TFLOPS, GB/s, etc.

    # Relationship
    gpu = relationship("GPU", back_populates="benchmarks")
