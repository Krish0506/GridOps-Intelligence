"""Pydantic schemas for Evidence Intelligence (Milestone 4)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeDocumentOut(BaseModel):
    document_id: str
    title: str
    category: str
    revision: str
    source_filename: str
    checksum: str


class KnowledgeChunkOut(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int | None
    text: str
    source_checksum: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    category: str | None = None
    equipment: str | None = None


class KnowledgeSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    title: str | None
    revision: str | None
    category: str | None
    page_number: int | None
    text: str
    semantic_score: float
    keyword_score: float
    combined_score: float
    source_checksum: str


class KnowledgeAskRequest(BaseModel):
    question: str = Field(min_length=1)
    asset_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class CitationOut(BaseModel):
    document_id: str | None
    title: str | None
    revision: str | None
    page_number: int | None
    chunk_id: str | None
    source_checksum: str | None
    excerpt: str | None


class KnowledgeAskResponse(BaseModel):
    question: str
    asset_id: str | None
    answer: str
    citations: list[CitationOut]
    key_facts: list[str]
    limitations: list[str]
    evidence_sufficient: bool
    confidence: str
    provider: str


class IngestionRunOut(BaseModel):
    run_id: str
    status: str
    documents_processed: int
    chunks_created: int
    error_count: int


__all__ = [
    "CitationOut",
    "IngestionRunOut",
    "KnowledgeAskRequest",
    "KnowledgeAskResponse",
    "KnowledgeChunkOut",
    "KnowledgeDocumentOut",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResult",
]
