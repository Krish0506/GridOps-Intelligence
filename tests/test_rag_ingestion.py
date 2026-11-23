"""Tests for Milestone 4 ingestion."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rag.documents import generate_corpus
from rag.embeddings import MockEmbeddingProvider
from rag.ingestion import ingest_directory
from rag.repository import InMemoryKnowledgeRepository


def test_ingestion_idempotent(tmp_path) -> None:
    source_dir = tmp_path / "docs"
    generate_corpus(source_dir)
    repository = InMemoryKnowledgeRepository()
    provider = MockEmbeddingProvider()
    first = ingest_directory(source_dir, repository, provider)
    second = ingest_directory(source_dir, repository, provider)
    assert first["documents_processed"] > 0
    assert second["documents_processed"] == 0
    assert len(repository.list_chunks()) == first["chunks_created"]


def test_ingestion_reprocesses_changed_checksum(tmp_path) -> None:
    source_dir = tmp_path / "docs"
    generate_corpus(source_dir)
    repository = InMemoryKnowledgeRepository()
    provider = MockEmbeddingProvider()
    ingest_directory(source_dir, repository, provider)
    target = next(path for path in source_dir.iterdir() if path.suffix == ".txt")
    target.write_text(target.read_text() + "\nchanged", encoding="utf-8")
    result = ingest_directory(source_dir, repository, provider)
    assert result["documents_processed"] >= 1


def test_ingestion_rejects_empty_file(tmp_path) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    (source_dir / "empty.txt").write_text("", encoding="utf-8")
    repository = InMemoryKnowledgeRepository()
    provider = MockEmbeddingProvider()
    result = ingest_directory(source_dir, repository, provider)
    assert result["error_count"] >= 1
    assert any("empty file" in error for error in result["errors"])
