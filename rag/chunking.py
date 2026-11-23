"""Chunking of extracted document text with provenance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    category: str
    revision: str
    page_number: int | None
    chunk_index: int
    text: str
    source_checksum: str


def chunk_text(
    document_id: str,
    title: str,
    category: str,
    revision: str,
    pages: list[tuple[int, str]],
    source_checksum: str,
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[Chunk]:
    """Split page text into overlapping word-based chunks."""
    chunks: list[Chunk] = []
    index = 0
    for page_number, page_text in pages:
        words = page_text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(len(words), start + chunk_size)
            chunk_words = words[start:end]
            if not chunk_words:
                break
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}-p{page_number}-c{index}",
                    document_id=document_id,
                    title=title,
                    category=category,
                    revision=revision,
                    page_number=page_number,
                    chunk_index=index,
                    text=" ".join(chunk_words),
                    source_checksum=source_checksum,
                )
            )
            index += 1
            if end >= len(words):
                break
            start = max(0, end - overlap)
    return chunks


__all__ = ["Chunk", "chunk_text"]
