"""risk records table

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-11-23 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, None] = "2b3c4d5e6f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.String(length=16), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("prediction_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("risk_category", sa.String(length=32), nullable=False),
        sa.Column("anomaly_score", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("model_probability", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("data_quality", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("primary_drivers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_records")),
    )
    op.create_index("ix_risk_records_asset_id", "risk_records", ["asset_id"], unique=False)
    op.create_index("ix_risk_records_risk_category", "risk_records", ["risk_category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_risk_records_risk_category", table_name="risk_records")
    op.drop_index("ix_risk_records_asset_id", table_name="risk_records")
    op.drop_table("risk_records")
