"""Knowledge-base REST API (Milestone 4)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from rag.embeddings import MockEmbeddingProvider
from rag.generation import MockGenerationProvider
from rag.ingestion import ingest_directory
from rag.repository import SQLAlchemyKnowledgeRepository
from rag.schemas import (
    IngestionRunOut,
    KnowledgeAskRequest,
    KnowledgeAskResponse,
    KnowledgeChunkOut,
    KnowledgeDocumentOut,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from rag.service import EvidenceService

router = APIRouter(prefix="/api/v1/knowledge")


def _service(session: Session) -> EvidenceService:
    repository = SQLAlchemyKnowledgeRepository(session)
    provider = MockEmbeddingProvider()
    generator = MockGenerationProvider()
    return EvidenceService(repository, provider, generator)


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(session: Session = Depends(get_db)):
    repository = SQLAlchemyKnowledgeRepository(session)
    return [
        KnowledgeDocumentOut(
            document_id=d.document_id,
            title=d.title,
            category=d.category,
            revision=d.revision,
            source_filename=d.source_filename,
            checksum=d.checksum,
        )
        for d in repository.list_documents()
    ]


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentOut)
def get_document(document_id: str, session: Session = Depends(get_db)):
    repository = SQLAlchemyKnowledgeRepository(session)
    document = repository.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return KnowledgeDocumentOut(
        document_id=document.document_id,
        title=document.title,
        category=document.category,
        revision=document.revision,
        source_filename=document.source_filename,
        checksum=document.checksum,
    )


@router.post("/ingestion", response_model=IngestionRunOut)
def trigger_ingestion(source_dir: str = "data/knowledge_base/source_documents", session: Session = Depends(get_db)):
    service = _service(session)
    result = service.ingest(Path(source_dir))
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
    from backend.app.models import KnowledgeIngestionRun
    from uuid import UUID

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
    results = service.search(request.query, top_k=request.top_k, category=request.category, equipment=request.equipment)
    return [
        KnowledgeSearchResult(
            chunk_id=item["chunk_id"],
            document_id=item["document_id"],
            title=item.get("title"),
            revision=item.get("revision"),
            category=item.get("category"),
            page_number=item.get("page_number"),
            text=item["text"],
            semantic_score=item["semantic_score"],
            keyword_score=item["keyword_score"],
            combined_score=item["combined_score"],
            source_checksum=item["source_checksum"],
        )
        for item in results
    ]


@router.post("/ask", response_model=KnowledgeAskResponse)
def ask_question(request: KnowledgeAskRequest, session: Session = Depends(get_db)):
    service = _service(session)
    result = service.ask(request.question, asset_id=request.asset_id, top_k=request.top_k)
    return KnowledgeAskResponse(
        question=result["question"],
        asset_id=result["asset_id"],
        answer=result["answer"],
        citations=result["citations"],
        key_facts=result["key_facts"],
        limitations=result["limitations"],
        evidence_sufficient=result["evidence_sufficient"],
        confidence=result["confidence"],
        provider=result["provider"],
    )


@router.post("/assets/{asset_id}/ask", response_model=KnowledgeAskResponse)
def ask_asset_question(asset_id: str, request: KnowledgeAskRequest, session: Session = Depends(get_db)):
    service = _service(session)
    result = service.ask(request.question, asset_id=asset_id, top_k=request.top_k)
    return KnowledgeAskResponse(
        question=result["question"],
        asset_id=result["asset_id"],
        answer=result["answer"],
        citations=result["citations"],
        key_facts=result["key_facts"],
        limitations=result["limitations"],
        evidence_sufficient=result["evidence_sufficient"],
        confidence=result["confidence"],
        provider=result["provider"],
    )


@router.get("/chunks/{chunk_id}", response_model=KnowledgeChunkOut)
def get_chunk(chunk_id: str, session: Session = Depends(get_db)):
    repository = SQLAlchemyKnowledgeRepository(session)
    chunk = repository.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    return KnowledgeChunkOut(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        page_number=chunk.page_number,
        text=chunk.text,
        source_checksum=chunk.source_checksum,
    )
