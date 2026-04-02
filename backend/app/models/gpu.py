from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class GPU(Base):
    __tablename__ = "gpus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    vendor = Column(String(20), nullable=False, index=True)  # NVIDIA / AMD
    generation = Column(String(50), nullable=False)  # Hopper, Blackwell, Instinct
    form_factor = Column(String(30), nullable=False)  # SXM, NVL72

    # Memory
    hbm_capacity_gb = Column(Float, nullable=False)
    hbm_type = Column(String(20))  # HBM3, HBM3e
    mem_bandwidth_tb_s = Column(Float, nullable=False)

    # Compute
    bf16_tflops = Column(Float)
    fp64_tflops = Column(Float)
    fp8_tflops = Column(Float)
    fp4_tflops = Column(Float)

    # Power & Cooling
    tdp_watts = Column(Integer)
    cooling_type = Column(String(20), default="air")  # air / liquid

    # Interconnect
    intra_node_interconnect = Column(String(50))  # NVLink 4, NVLink 5, IF v3, etc.
    interconnect_bw_gb_s = Column(Float)

    # Scale
    max_gpus_per_node = Column(Integer, default=8)
    is_rack_scale = Column(Boolean, default=False)  # True for NVL72 configs
    rack_gpu_count = Column(Integer)  # 72 for NVL72
    rack_fabric_bw_tb_s = Column(Float)  # 130 TB/s for GB200 NVL72

    # Pricing & Status
    msrp_usd = Column(Float)
    is_estimated = Column(Boolean, default=False)
    release_date = Column(String(20))

    # Verdict (from HTML)
    verdict = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    benchmarks = relationship("Benchmark", back_populates="gpu", cascade="all, delete-orphan")
    availability = relationship("Availability", back_populates="gpu", uselist=False, cascade="all, delete-orphan")
