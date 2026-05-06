"""Add msrp_as_of date stamp to gpus

Revision ID: 003_add_msrp_as_of
Revises: 002_add_nvlink_topology
Create Date: 2026-05-06 09:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_add_msrp_as_of"
down_revision: Union[str, None] = "002_add_nvlink_topology"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gpus", sa.Column("msrp_as_of", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("gpus", "msrp_as_of")
