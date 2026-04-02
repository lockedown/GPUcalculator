from sqlalchemy import Column, Float, Integer, String

from app.db.database import Base


class Networking(Base):
    __tablename__ = "networking"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    type = Column(String(50), nullable=False)  # NVLink4, NVLink5, NVL72, IF_v3, IF_v4, IB_NDR, IB_XDR, RoCEv2
    vendor = Column(String(20), nullable=False)  # NVIDIA, AMD, Mellanox, Generic
    generation = Column(String(30))

    bandwidth_gb_s = Column(Float, nullable=False)
    latency_us = Column(Float)
    is_inter_node = Column(Integer, default=0)  # 0 = intra-node, 1 = inter-node
    notes = Column(String(500))
