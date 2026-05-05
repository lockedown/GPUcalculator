"""Add nvlink_topology field to gpus

Revision ID: 002_add_nvlink_topology
Revises: 001_add_gpu_memory_and_workload_fields
Create Date: 2026-05-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_add_nvlink_topology"
down_revision: Union[str, None] = "001_add_gpu_memory_and_workload_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gpus", sa.Column("nvlink_topology", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("gpus", "nvlink_topology")
