"""Tests for Milestone 4 embeddings."""

from __future__ import annotations

from rag.embeddings import MockEmbeddingProvider, cosine_similarity


def test_mock_embedding_dimensions() -> None:
    provider = MockEmbeddingProvider(dimension=8)
    vectors = provider.embed(["hello", "world"])
    assert len(vectors) == 2
    assert all(len(vector) == 8 for vector in vectors)


def test_cosine_similarity_identical() -> None:
    vector = [1.0, 2.0, 3.0]
    assert cosine_similarity(vector, vector) > 0.99
