"""Citation validation for grounded answers."""

from __future__ import annotations


def validate_citations(citations: list[dict], retrieved: list[dict]) -> list[dict]:
    """Validate that every citation maps to a retrieved chunk.

    Returns the validated citations (subset of retrieved).  Invalid citations
    are dropped, never invented.
    """
    retrieved_ids = {item.get("chunk_id") for item in retrieved}
    validated: list[dict] = []
    for citation in citations:
        if citation.get("chunk_id") in retrieved_ids:
            validated.append(citation)
    return validated


def citations_from_retrieval(retrieved: list[dict]) -> list[dict]:
    """Build citation records from retrieved chunks (never from model output)."""
    citations: list[dict] = []
    for item in retrieved:
        citations.append(
            {
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "revision": item.get("revision"),
                "page_number": item.get("page_number"),
                "chunk_id": item.get("chunk_id"),
                "source_filename": None,
                "source_checksum": item.get("source_checksum"),
                "excerpt": (item.get("text") or "")[:240],
            }
        )
    return citations


__all__ = ["citations_from_retrieval", "validate_citations"]
