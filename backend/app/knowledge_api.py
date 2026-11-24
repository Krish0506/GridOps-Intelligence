"""Knowledge-base and Evidence Intelligence REST API."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.knowledge_routing import route_question
from backend.app.models import DocumentChunk, KnowledgeDocument, KnowledgeIngestionRun
from rag.embeddings import MockEmbeddingProvider
from rag.generation import MockGenerationProvider
from rag.ingestion import ingest_directory
from rag.repository import SQLAlchemyKnowledgeRepository
from rag.schemas import (
    CitationOut,
    IngestionRunOut,
    KnowledgeAskRequest,
    KnowledgeAskResponse,
    KnowledgeChunkOut,
    KnowledgeDocumentContentOut,
    KnowledgeDocumentOut,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
    StructuredAnswerOut,
)
from rag.service import EvidenceService

router = APIRouter(prefix="/api/v1/knowledge")


def _service(session: Session) -> EvidenceService:
    repository = SQLAlchemyKnowledgeRepository(session)
    provider = MockEmbeddingProvider()
    generator = MockGenerationProvider()
    return EvidenceService(repository, provider, generator)


def _document_out(session: Session, row: KnowledgeDocument) -> KnowledgeDocumentOut:
    chunk_count = int(
        session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == row.document_id)
        )
        or 0
    )
    return KnowledgeDocumentOut(
        document_id=row.document_id,
        title=row.title,
        category=row.category,
        revision=row.revision,
        source_filename=row.source_filename,
        checksum=row.checksum,
        equipment_applicability=row.equipment_applicability,
        publication_date=None if row.publication_date is None else row.publication_date.isoformat(),
        mime_type=row.mime_type,
        chunk_count=chunk_count,
    )


def _chunk_out(chunk, document_title: str | None = None) -> KnowledgeChunkOut:
    return KnowledgeChunkOut(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        page_number=chunk.page_number,
        text=chunk.text,
        source_checksum=chunk.source_checksum,
        document_title=document_title or chunk.metadata.get("title"),
        category=chunk.metadata.get("category"),
        equipment=chunk.metadata.get("equipment"),
    )


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    category: str | None = Query(default=None, max_length=64),
    equipment: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=128),
    session: Session = Depends(get_db),
):
    statement = select(KnowledgeDocument)
    if category:
        statement = statement.where(KnowledgeDocument.category == category)
    if equipment:
        statement = statement.where(
            (KnowledgeDocument.equipment_applicability == equipment)
            | (KnowledgeDocument.equipment_applicability == "all")
            | (KnowledgeDocument.equipment_applicability.is_(None))
        )
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            KnowledgeDocument.title.ilike(term)
            | KnowledgeDocument.document_id.ilike(term)
            | KnowledgeDocument.extracted_text.ilike(term)
        )
    rows = session.scalars(statement.order_by(KnowledgeDocument.title, KnowledgeDocument.document_id)).all()
    return [_document_out(session, row) for row in rows]


@router.get("/stats")
def knowledge_stats(session: Session = Depends(get_db)):
    documents = int(session.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0)
    chunks = int(session.scalar(select(func.count()).select_from(DocumentChunk)) or 0)
    categories = [
        {"category": category, "documents": count}
        for category, count in session.execute(
            select(KnowledgeDocument.category, func.count())
            .group_by(KnowledgeDocument.category)
            .order_by(KnowledgeDocument.category)
        )
    ]
    equipment = [
        {"equipment": equipment or "all", "documents": count}
        for equipment, count in session.execute(
            select(KnowledgeDocument.equipment_applicability, func.count())
            .group_by(KnowledgeDocument.equipment_applicability)
            .order_by(KnowledgeDocument.equipment_applicability)
        )
    ]
    formats = [
        {"mime_type": mime_type, "documents": count}
        for mime_type, count in session.execute(
            select(KnowledgeDocument.mime_type, func.count())
            .group_by(KnowledgeDocument.mime_type)
            .order_by(KnowledgeDocument.mime_type)
        )
    ]
    latest_run = (
        session.scalars(
            select(KnowledgeIngestionRun)
            .where(KnowledgeIngestionRun.documents_processed > 0)
            .order_by(KnowledgeIngestionRun.started_at.desc())
            .limit(1)
        ).first()
        or session.scalars(
            select(KnowledgeIngestionRun).order_by(KnowledgeIngestionRun.started_at.desc()).limit(1)
        ).first()
    )
    return {
        "documents": documents,
        "chunks": chunks,
        "categories": categories,
        "equipment": equipment,
        "formats": formats,
        "latest_ingestion": None
        if latest_run is None
        else {
            "run_id": str(latest_run.run_id),
            "status": latest_run.status,
            "started_at": latest_run.started_at.isoformat(),
            "completed_at": None if latest_run.completed_at is None else latest_run.completed_at.isoformat(),
            "documents_processed": latest_run.documents_processed,
            "chunks_created": latest_run.chunks_created,
            "error_count": latest_run.error_count,
        },
        "synthetic": True,
        "limitations": [
            "Synthetic demonstration documents; not official engineering standards.",
            "Embeddings use the deterministic offline mock provider, not a production embedding model.",
            "PDF extraction is lightweight and does not perform OCR.",
        ],
    }


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentOut)
def get_document(document_id: str, session: Session = Depends(get_db)):
    row = session.get(KnowledgeDocument, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _document_out(session, row)


@router.get("/documents/{document_id}/content", response_model=KnowledgeDocumentContentOut)
def get_document_content(document_id: str, session: Session = Depends(get_db)):
    row = session.get(KnowledgeDocument, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    base = _document_out(session, row)
    return KnowledgeDocumentContentOut(
        **base.model_dump(),
        extracted_text=row.extracted_text,
        chunks=[
            KnowledgeChunkOut(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                page_number=chunk.page_number,
                text=chunk.text,
                source_checksum=chunk.source_checksum,
                document_title=row.title,
                category=row.category,
                equipment=row.equipment_applicability,
            )
            for chunk in chunks
        ],
    )


@router.post("/ingestion", response_model=IngestionRunOut)
def trigger_ingestion(
    source_dir: str = "data/knowledge_base/source_documents",
    force: bool = False,
    session: Session = Depends(get_db),
):
    service = _service(session)
    result = service.ingest(Path(source_dir), force=force)
    session.commit()
    return IngestionRunOut(
        run_id=result["run_id"],
        status=result["status"],
        documents_processed=result["documents_processed"],
        chunks_created=result["chunks_created"],
        error_count=result["error_count"],
    )


@router.get("/ingestion/{run_id}", response_model=IngestionRunOut)
def get_ingestion_status(run_id: str, session: Session = Depends(get_db)):
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="ingestion run not found")
    row = session.get(KnowledgeIngestionRun, run_uuid)
    if row is None:
        raise HTTPException(status_code=404, detail="ingestion run not found")
    return IngestionRunOut(
        run_id=str(row.run_id),
        status=row.status,
        documents_processed=row.documents_processed,
        chunks_created=row.chunks_created,
        error_count=row.error_count,
    )


@router.post("/search", response_model=list[KnowledgeSearchResult])
def search_evidence(request: KnowledgeSearchRequest, session: Session = Depends(get_db)):
    service = _service(session)
    results = service.search(
        request.query,
        top_k=request.top_k,
        category=request.category,
        equipment=request.equipment,
    )
    return [
        KnowledgeSearchResult(
            chunk_id=item["chunk_id"],
            document_id=item["document_id"],
            title=item.get("title"),
            revision=item.get("revision"),
            category=item.get("category"),
            equipment=item.get("equipment"),
            page_number=item.get("page_number"),
            text=item["text"],
            semantic_score=item["semantic_score"],
            keyword_score=item["keyword_score"],
            combined_score=item["combined_score"],
            source_checksum=item["source_checksum"],
        )
        for item in results
    ]


def _ask(
    session: Session,
    request: KnowledgeAskRequest,
    *,
    asset_id: str | None,
) -> KnowledgeAskResponse:
    structured = route_question(session, request.question)
    if structured is not None:
        return KnowledgeAskResponse(
            question=request.question,
            asset_id=asset_id,
            answer=structured["text"],
            citations=[],
            key_facts=[structured["text"]],
            limitations=[
                "Answered from the structured synthetic PostgreSQL dataset, not from engineering documents.",
                "Counts reflect the current local demonstration database.",
            ],
            evidence_sufficient=True,
            confidence="high",
            provider="structured-postgres",
            route="structured_database",
            structured_data=StructuredAnswerOut(
                metric=structured["metric"],
                value=structured["value"],
                text=structured["text"],
                breakdown=structured.get("breakdown") or {},
            ),
        )

    service = _service(session)
    result = service.ask(
        request.question,
        asset_id=asset_id,
        top_k=request.top_k,
        category=request.category,
        equipment=request.equipment,
    )
    return KnowledgeAskResponse(
        question=result["question"],
        asset_id=result["asset_id"],
        answer=result["answer"],
        citations=[CitationOut(**citation) for citation in result["citations"]],
        key_facts=result["key_facts"],
        limitations=result["limitations"],
        evidence_sufficient=result["evidence_sufficient"],
        confidence=result["confidence"],
        provider=result["provider"],
        route="document_retrieval",
        structured_data=None,
    )


@router.post("/ask", response_model=KnowledgeAskResponse)
def ask_question(request: KnowledgeAskRequest, session: Session = Depends(get_db)):
    return _ask(session, request, asset_id=request.asset_id)


@router.post("/assets/{asset_id}/ask", response_model=KnowledgeAskResponse)
def ask_asset_question(asset_id: str, request: KnowledgeAskRequest, session: Session = Depends(get_db)):
    return _ask(session, request, asset_id=asset_id)


@router.get("/chunks/{chunk_id}", response_model=KnowledgeChunkOut)
def get_chunk(chunk_id: str, session: Session = Depends(get_db)):
    repository = SQLAlchemyKnowledgeRepository(session)
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    document = session.get(KnowledgeDocument, chunk.document_id)
    return _chunk_out(chunk, None if document is None else document.title)
