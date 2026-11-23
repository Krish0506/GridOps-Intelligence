"""engineering decision workflow tables

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-11-22 21:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "2b3c4d5e6f7a"
down_revision: Union[str, None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engineering_decisions",
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.String(length=16), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("predicted_risk_probability", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("risk_category", sa.String(length=32), nullable=True),
        sa.Column("anomaly_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("decision_status", sa.String(length=32), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("replacement_risk_category", sa.String(length=32), nullable=True),
        sa.Column("review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer", sa.String(length=128), nullable=False, server_default="demo-reviewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "decision_status IN ('PENDING_REVIEW', 'IN_REVIEW', 'APPROVED', 'REJECTED', 'OVERRIDDEN', 'ESCALATED', 'DEFERRED')",
            name=op.f("ck_engineering_decisions_decision_status"),
        ),
        sa.PrimaryKeyConstraint("decision_id", name=op.f("pk_engineering_decisions")),
    )
    op.create_index("ix_engineering_decisions_asset_id", "engineering_decisions", ["asset_id"], unique=False)
    op.create_index("ix_engineering_decisions_status", "engineering_decisions", ["decision_status"], unique=False)

    op.create_table(
        "decision_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("document_title", sa.String(length=256), nullable=False),
        sa.Column("revision", sa.String(length=32), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["decision_id"], ["engineering_decisions.decision_id"], ondelete="CASCADE", name=op.f("fk_decision_evidence_decision_id_engineering_decisions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_evidence")),
    )
    op.create_index("ix_decision_evidence_decision_id", "decision_evidence", ["decision_id"], unique=False)

    op.create_table(
        "decision_events",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reviewer", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("prediction_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["decision_id"], ["engineering_decisions.decision_id"], ondelete="CASCADE", name=op.f("fk_decision_events_decision_id_engineering_decisions")),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_decision_events")),
    )
    op.create_index("ix_decision_events_decision_id", "decision_events", ["decision_id"], unique=False)
    op.create_index("ix_decision_events_timestamp", "decision_events", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_decision_events_timestamp", table_name="decision_events")
    op.drop_index("ix_decision_events_decision_id", table_name="decision_events")
    op.drop_table("decision_events")
    op.drop_index("ix_decision_evidence_decision_id", table_name="decision_evidence")
    op.drop_table("decision_evidence")
    op.drop_index("ix_engineering_decisions_status", table_name="engineering_decisions")
    op.drop_index("ix_engineering_decisions_asset_id", table_name="engineering_decisions")
    op.drop_table("engineering_decisions")
