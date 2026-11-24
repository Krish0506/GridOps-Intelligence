"""widen risk_records anomaly_score

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-11-23 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4d5e6f7a8b9c"
down_revision: Union[str, None] = "3c4d5e6f7a8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "risk_records",
        "anomaly_score",
        existing_type=sa.Numeric(precision=12, scale=4),
        type_=sa.Numeric(precision=18, scale=4),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "risk_records",
        "anomaly_score",
        existing_type=sa.Numeric(precision=18, scale=4),
        type_=sa.Numeric(precision=12, scale=4),
        existing_nullable=True,
    )
