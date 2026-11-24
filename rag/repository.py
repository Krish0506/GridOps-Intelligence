"""Knowledge-base repository abstraction (in-memory and SQLAlchemy)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from backend.app.models import DocumentChunk as DocumentChunkModel
from backend.app.models import KnowledgeDocument as KnowledgeDocumentModel
from backend.app.models import KnowledgeIngestionRun as KnowledgeIngestionRunModel


@dataclass
class KnowledgeDocumentRecord:
    document_id: str
    source_filename: str
    checksum: str
    mime_type: str
    title: str
    category: str
    revision: str
    publication_date: str | None
    equipment_applicability: str | None
    extracted_text: str
    status: str = "ingested"


@dataclass
class DocumentChunkRecord:
    chunk_id: str
    document_id: str
    chunk_index: int
    page_number: int | None
    text: str
    embedding: list[float]
    embedding_model: str
    embedding_dim: int
    source_checksum: str
    metadata: dict


@dataclass
class IngestionRunRecord:
    run_id: str
    status: str
    documents_processed: int = 0
    chunks_created: int = 0
    error_count: int = 0
    error_summary: str | None = None


class KnowledgeRepository(Protocol):
    def upsert_document(self, document: KnowledgeDocumentRecord) -> None: ...
    def get_document(self, document_id: str) -> KnowledgeDocumentRecord | None: ...
    def list_documents(self) -> list[KnowledgeDocumentRecord]: ...
    def delete_chunks_for_document(self, document_id: str) -> None: ...
    def add_chunks(self, chunks: list[DocumentChunkRecord]) -> None: ...
    def list_chunks(self) -> list[DocumentChunkRecord]: ...
    def get_chunk(self, chunk_id: str) -> DocumentChunkRecord | None: ...
    def create_ingestion_run(self) -> IngestionRunRecord: ...
    def complete_ingestion_run(self, run: IngestionRunRecord, status: str, error_summary: str | None = None) -> None: ...


class InMemoryKnowledgeRepository:
    """In-memory repository used by tests and offline development."""

    def __init__(self) -> None:
        self.documents: dict[str, KnowledgeDocumentRecord] = {}
        self.chunks: dict[str, DocumentChunkRecord] = {}
        self.runs: dict[str, IngestionRunRecord] = {}

    def upsert_document(self, document: KnowledgeDocumentRecord) -> None:
        self.documents[document.document_id] = document

    def get_document(self, document_id: str) -> KnowledgeDocumentRecord | None:
        return self.documents.get(document_id)

    def list_documents(self) -> list[KnowledgeDocumentRecord]:
        return sorted(self.documents.values(), key=lambda d: d.document_id)

    def delete_chunks_for_document(self, document_id: str) -> None:
        to_delete = [cid for cid, chunk in self.chunks.items() if chunk.document_id == document_id]
        for cid in to_delete:
            del self.chunks[cid]

    def add_chunks(self, chunks: list[DocumentChunkRecord]) -> None:
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk

    def list_chunks(self) -> list[DocumentChunkRecord]:
        return list(self.chunks.values())

    def get_chunk(self, chunk_id: str) -> DocumentChunkRecord | None:
        return self.chunks.get(chunk_id)

    def create_ingestion_run(self) -> IngestionRunRecord:
        run = IngestionRunRecord(run_id=str(uuid.uuid4()), status="running")
        self.runs[run.run_id] = run
        return run

    def complete_ingestion_run(self, run: IngestionRunRecord, status: str, error_summary: str | None = None) -> None:
        run.status = status
        run.error_summary = error_summary
        self.runs[run.run_id] = run


class SQLAlchemyKnowledgeRepository:
    """SQLAlchemy-backed repository for production use."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_document(self, document: KnowledgeDocumentRecord) -> None:
        existing = self.session.get(KnowledgeDocumentModel, document.document_id)
        if existing is None:
            existing = KnowledgeDocumentModel(document_id=document.document_id)
            self.session.add(existing)
        existing.source_filename = document.source_filename
        existing.checksum = document.checksum
        existing.mime_type = document.mime_type
        existing.title = document.title
        existing.category = document.category
        existing.revision = document.revision
        existing.equipment_applicability = document.equipment_applicability
        if document.publication_date:
            try:
                from datetime import date

                existing.publication_date = date.fromisoformat(document.publication_date[:10])
            except (TypeError, ValueError):
                existing.publication_date = None
        existing.extracted_text = document.extracted_text
        existing.status = document.status
        self.session.flush()

    def get_document(self, document_id: str) -> KnowledgeDocumentRecord | None:
        row = self.session.get(KnowledgeDocumentModel, document_id)
        if row is None:
            return None
        return _document_from_row(row)

    def list_documents(self) -> list[KnowledgeDocumentRecord]:
        rows = self.session.query(KnowledgeDocumentModel).order_by(KnowledgeDocumentModel.document_id).all()
        return [_document_from_row(row) for row in rows]

    def delete_chunks_for_document(self, document_id: str) -> None:
        self.session.query(DocumentChunkModel).filter(DocumentChunkModel.document_id == document_id).delete()
        self.session.flush()

    def add_chunks(self, chunks: list[DocumentChunkRecord]) -> None:
        for chunk in chunks:
            row = DocumentChunkModel(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                embedding=json.dumps(chunk.embedding),
                embedding_model=chunk.embedding_model,
                embedding_dim=chunk.embedding_dim,
                source_checksum=chunk.source_checksum,
                chunk_metadata=chunk.metadata,
            )
            self.session.add(row)
        self.session.flush()

    def list_chunks(self) -> list[DocumentChunkRecord]:
        rows = self.session.query(DocumentChunkModel).all()
        return [_chunk_from_row(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> DocumentChunkRecord | None:
        row = self.session.get(DocumentChunkModel, chunk_id)
        if row is None:
            return None
        return _chunk_from_row(row)

    def create_ingestion_run(self) -> IngestionRunRecord:
        row = KnowledgeIngestionRunModel(status="running")
        self.session.add(row)
        self.session.flush()
        return IngestionRunRecord(run_id=str(row.run_id), status="running")

    def complete_ingestion_run(self, run: IngestionRunRecord, status: str, error_summary: str | None = None) -> None:
        row = self.session.get(KnowledgeIngestionRunModel, run.run_id)
        if row is not None:
            row.status = status
            row.error_summary = error_summary
            from datetime import datetime, timezone

            row.completed_at = datetime.now(timezone.utc)
            self.session.flush()
        run.status = status
        run.error_summary = error_summary


def _document_from_row(row: KnowledgeDocumentModel) -> KnowledgeDocumentRecord:
    return KnowledgeDocumentRecord(
        document_id=row.document_id,
        source_filename=row.source_filename,
        checksum=row.checksum,
        mime_type=row.mime_type,
        title=row.title,
        category=row.category,
        revision=row.revision,
        publication_date=None if row.publication_date is None else row.publication_date.isoformat(),
        equipment_applicability=row.equipment_applicability,
        extracted_text=row.extracted_text,
        status=row.status,
    )


def _chunk_from_row(row: DocumentChunkModel) -> DocumentChunkRecord:
    return DocumentChunkRecord(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        chunk_index=row.chunk_index,
        page_number=row.page_number,
        text=row.text,
        embedding=json.loads(row.embedding),
        embedding_model=row.embedding_model,
        embedding_dim=row.embedding_dim,
        source_checksum=row.source_checksum,
        metadata=row.chunk_metadata or {},
    )


__all__ = [
    "DocumentChunkRecord",
    "InMemoryKnowledgeRepository",
    "IngestionRunRecord",
    "KnowledgeDocumentRecord",
    "KnowledgeRepository",
    "SQLAlchemyKnowledgeRepository",
]
