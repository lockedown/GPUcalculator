from sqlalchemy import Column, Integer, String, Text

from app.db.database import Base


class SoftwareStack(Base):
    __tablename__ = "software_stacks"

    id = Column(Integer, primary_key=True, index=True)
    gpu_vendor = Column(String(20), nullable=False, index=True)  # NVIDIA, AMD
    stack_name = Column(String(100), nullable=False)  # CUDA, ROCm, TensorRT-LLM, vLLM, etc.
    maturity_score = Column(Integer, nullable=False)  # 1-10
    framework_support = Column(String(200))  # comma-separated: PyTorch, JAX, TensorFlow
    fp8_support_level = Column(String(20), default="none")  # none, partial, full
    notes = Column(Text)
