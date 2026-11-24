"""Hybrid retrieval and reranking for engineering evidence."""

from __future__ import annotations

from rag.embeddings import cosine_similarity
from rag.repository import DocumentChunkRecord, KnowledgeRepository


def search(
    repository: KnowledgeRepository,
    query: str,
    provider,
    *,
    top_k: int = 5,
    category: str | None = None,
    equipment: str | None = None,
    semantic_weight: float = 0.5,
    keyword_weight: float = 0.5,
) -> list[dict]:
    """Hybrid retrieval using semantic similarity, keyword overlap, and metadata filters."""
    chunks = repository.list_chunks()
    if category:
        wanted_category = category.strip().lower()
        chunks = [
            chunk
            for chunk in chunks
            if str(chunk.metadata.get("category") or "").strip().lower() == wanted_category
        ]
    if equipment:
        wanted_equipment = equipment.strip().lower().replace(" ", "_")
        filtered = []
        for chunk in chunks:
            applicability = str(chunk.metadata.get("equipment") or "all").strip().lower().replace(" ", "_")
            if applicability in {"all", "any", "all_equipment", wanted_equipment}:
                filtered.append(chunk)
        chunks = filtered

    query_vector = provider.embed([query])[0]
    results: list[dict] = []
    for chunk in chunks:
        semantic_score = cosine_similarity(query_vector, chunk.embedding)
        keyword_score = _keyword_score(query, chunk.text)
        combined = semantic_weight * semantic_score + keyword_weight * keyword_score
        results.append(
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "title": chunk.metadata.get("title"),
                "revision": chunk.metadata.get("revision"),
                "category": chunk.metadata.get("category"),
                "equipment": chunk.metadata.get("equipment"),
                "page_number": chunk.page_number,
                "text": chunk.text,
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "combined_score": combined,
                "source_checksum": chunk.source_checksum,
            }
        )
    results.sort(key=lambda item: item["combined_score"], reverse=True)
    return results[:top_k]


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "should",
    "that", "the", "this", "to", "what", "when", "where", "which", "why",
    "with", "would",
}


def _keyword_score(query: str, text: str) -> float:
    query_terms = {
        term.strip(" ,.;:()[]?!").lower()
        for term in query.split()
        if term.strip(" ,.;:()[]?!").lower() not in STOPWORDS
    }
    query_terms.discard("")
    text_terms = {
        term.strip(" ,.;:()[]?!").lower() for term in text.split()
    }
    if not query_terms or not text_terms:
        return 0.0
    overlap = len(query_terms & text_terms)
    return overlap / len(query_terms)


def rerank(results: list[dict]) -> list[dict]:
    """Lightweight reranking using combined score plus keyword overlap boost."""
    for result in results:
        result["rerank_score"] = result["combined_score"] + 0.1 * result.get("keyword_score", 0.0)
    results.sort(key=lambda item: item["rerank_score"], reverse=True)
    return results


__all__ = ["rerank", "search"]
