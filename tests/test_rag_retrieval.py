"""Tests for Milestone 4 retrieval, reranking, generation, and asset integration."""

from __future__ import annotations

import tempfile

from rag.asset_integration import equipment_filter_for_asset
from rag.citations import citations_from_retrieval, validate_citations
from rag.documents import generate_corpus
from rag.embeddings import MockEmbeddingProvider
from rag.generation import MockGenerationProvider, build_prompt
from rag.ingestion import ingest_directory
from rag.repository import InMemoryKnowledgeRepository
from rag.retrieval import rerank, search
from rag.service import EvidenceService


def _service(tmp_path):
    source_dir = tmp_path / "docs"
    generate_corpus(source_dir)
    repository = InMemoryKnowledgeRepository()
    provider = MockEmbeddingProvider()
    ingest_directory(source_dir, repository, provider)
    return EvidenceService(repository, provider, MockGenerationProvider()), source_dir


def test_search_returns_results() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        service, _ = _service(__import__("pathlib").Path(tmp))
        results = service.search("transformer maintenance", top_k=3)
        assert len(results) > 0
        assert all("combined_score" in result for result in results)


def test_rerank_stable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        service, _ = _service(__import__("pathlib").Path(tmp))
        results = service.search("transformer", top_k=5)
        reranked = rerank(list(results))
        assert len(reranked) == len(results)


def test_ask_returns_citations() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        service, _ = _service(__import__("pathlib").Path(tmp))
        result = service.ask("Why might this transformer be high risk?", asset_id="T-00001")
        assert result["answer"]
        assert isinstance(result["citations"], list)
        assert result["evidence_sufficient"] is True
        assert result["provider"] == "mock-generator"


def test_insufficient_evidence_response() -> None:
    repository = InMemoryKnowledgeRepository()
    provider = MockEmbeddingProvider()
    service = EvidenceService(repository, provider, MockGenerationProvider())
    result = service.ask("What is the meaning of life?")
    assert result["evidence_sufficient"] is False
    assert "Insufficient evidence" in result["answer"]


def test_citation_validation_drops_invalid() -> None:
    retrieved = [{"chunk_id": "c1", "text": "hello"}]
    citations = [{"chunk_id": "c1"}, {"chunk_id": "fake"}]
    validated = validate_citations(citations, retrieved)
    assert len(validated) == 1
    assert validated[0]["chunk_id"] == "c1"


def test_citations_from_retrieval() -> None:
    retrieved = [{"chunk_id": "c1", "document_id": "D1", "title": "T", "revision": "R", "page_number": 1, "source_checksum": "abc", "text": "hello world"}]
    citations = citations_from_retrieval(retrieved)
    assert citations[0]["chunk_id"] == "c1"
    assert citations[0]["excerpt"] == "hello world"


def test_asset_equipment_filter() -> None:
    assert equipment_filter_for_asset("T-00001") == "transformers"
    assert equipment_filter_for_asset("CB-00001") == "circuit_breakers"
    assert equipment_filter_for_asset("UNKNOWN") is None


def test_build_prompt_contains_evidence() -> None:
    prompt = build_prompt("Q?", [{"text": "Evidence text"}])
    assert "Question: Q?" in prompt
    assert "Evidence text" in prompt
