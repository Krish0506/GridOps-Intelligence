"""Knowledge-base ingestion pipeline."""

from __future__ import annotations

import hashlib
from pathlib import Path

from rag.chunking import chunk_text
from rag.embeddings import EmbeddingProvider
from rag.extraction import extract_text
from rag.repository import DocumentChunkRecord, InMemoryKnowledgeRepository, KnowledgeDocumentRecord, KnowledgeRepository


SUPPORTED_SUFFIXES = {".txt", ".docx", ".pdf"}


def ingest_directory(
    source_dir: Path,
    repository: KnowledgeRepository,
    provider: EmbeddingProvider,
    *,
    max_file_size_bytes: int = 10 * 1024 * 1024,
) -> dict:
    """Ingest all supported documents in ``source_dir`` into the repository."""
    run = repository.create_ingestion_run()
    documents_processed = 0
    chunks_created = 0
    errors: list[str] = []

    for path in sorted(source_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            if path.stat().st_size > max_file_size_bytes:
                raise ValueError(f"file too large: {path.name}")
            if path.stat().st_size == 0:
                raise ValueError(f"empty file: {path.name}")
            checksum = _sha256(path)
            existing = repository.get_document(path.name)
            if existing is not None and existing.checksum == checksum:
                continue
            text, pages = extract_text(path)
            if not text.strip():
                raise ValueError(f"no text extracted: {path.name}")
            title = path.stem
            category = "Engineering"
            revision = "Rev A"
            mime_type = _mime_type(path.suffix.lower())
            document = KnowledgeDocumentRecord(
                document_id=path.name,
                source_filename=path.name,
                checksum=checksum,
                mime_type=mime_type,
                title=title,
                category=category,
                revision=revision,
                publication_date=None,
                equipment_applicability=None,
                extracted_text=text,
                status="ingested",
            )
            repository.upsert_document(document)
            repository.delete_chunks_for_document(document.document_id)
            chunks = chunk_text(
                document_id=document.document_id,
                title=document.title,
                category=document.category,
                revision=document.revision,
                pages=pages,
                source_checksum=checksum,
            )
            embeddings = provider.embed([chunk.text for chunk in chunks]) if chunks else []
            records = [
                DocumentChunkRecord(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    embedding=embeddings[index],
                    embedding_model=provider.model_name,
                    embedding_dim=provider.dimension,
                    source_checksum=chunk.source_checksum,
                    metadata={
                        "title": chunk.title,
                        "category": chunk.category,
                        "revision": chunk.revision,
                        "page_number": chunk.page_number,
                    },
                )
                for index, chunk in enumerate(chunks)
            ]
            repository.add_chunks(records)
            documents_processed += 1
            chunks_created += len(records)
        except Exception as exc:  # noqa: BLE001 - batch must continue
            errors.append(f"{path.name}: {exc}")

    status = "completed" if not errors else "completed_with_errors"
    error_summary = "; ".join(errors) if errors else None
    repository.complete_ingestion_run(run, status, error_summary)
    run.documents_processed = documents_processed
    run.chunks_created = chunks_created
    run.error_count = len(errors)
    return {
        "run_id": run.run_id,
        "status": status,
        "documents_processed": documents_processed,
        "chunks_created": chunks_created,
        "error_count": len(errors),
        "errors": errors,
    }


def _sha256(path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mime_type(suffix: str) -> str:
    return {
        ".txt": "text/plain",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")


__all__ = ["SUPPORTED_SUFFIXES", "ingest_directory"]
