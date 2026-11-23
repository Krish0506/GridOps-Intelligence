"""knowledge base tables

Revision ID: 0a1b2c3d4e5f
Revises: 04b9afe7bc6a
Create Date: 2026-11-22 20:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, None] = "04b9afe7bc6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("source_filename", sa.String(length=256), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.String(length=32), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("equipment_applicability", sa.String(length=64), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ingested"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_knowledge_documents")),
    )
    op.create_index("ix_knowledge_documents_category", "knowledge_documents", ["category"], unique=False)
    op.create_index("ix_knowledge_documents_checksum", "knowledge_documents", ["checksum"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=32), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=64), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.document_id"], ondelete="CASCADE", name=op.f("fk_document_chunks_document_id_knowledge_documents")),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_document_chunks")),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False)
    op.create_index("ix_document_chunks_checksum", "document_chunks", ["source_checksum"], unique=False)

    op.create_table(
        "knowledge_ingestion_runs",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("documents_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_knowledge_ingestion_runs")),
    )
    op.create_index("ix_knowledge_ingestion_runs_started_at", "knowledge_ingestion_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_ingestion_runs_started_at", table_name="knowledge_ingestion_runs")
    op.drop_table("knowledge_ingestion_runs")
    op.drop_index("ix_document_chunks_checksum", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_knowledge_documents_checksum", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_category", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
