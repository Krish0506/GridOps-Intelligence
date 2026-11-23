"""Tests for Milestone 4 document extraction and chunking."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rag.chunking import chunk_text
from rag.documents import generate_corpus
from rag.extraction import extract_text


def test_generate_corpus_creates_three_formats(tmp_path) -> None:
    manifest = generate_corpus(tmp_path)
    assert len(manifest) == 12 * 3
    formats = {entry["format"] for entry in manifest}
    assert formats == {"txt", "docx", "pdf"}


def test_txt_extraction(tmp_path) -> None:
    (tmp_path / "sample.txt").write_text("Hello world. This is a test.", encoding="utf-8")
    text, pages = extract_text(tmp_path / "sample.txt")
    assert "Hello world" in text
    assert pages == [(1, text)]


def test_docx_extraction(tmp_path) -> None:
    import zipfile

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Hello DOCX</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(tmp_path / "sample.docx", "w") as archive:
        archive.writestr("word/document.xml", xml)
    text, pages = extract_text(tmp_path / "sample.docx")
    assert "Hello DOCX" in text


def test_pdf_extraction(tmp_path) -> None:
    from rag.documents import _write_pdf

    _write_pdf(tmp_path / "sample.pdf", {"document_id": "D", "title": "T", "category": "C", "revision": "R", "equipment": "all", "body": "Hello PDF body"})
    text, pages = extract_text(tmp_path / "sample.pdf")
    assert "Hello" in text or "PDF" in text


def test_chunking_produces_chunks() -> None:
    pages = [(1, "one two three four five six seven eight nine ten")]
    chunks = chunk_text("DOC-1", "Title", "Cat", "Rev A", pages, "checksum", chunk_size=4, overlap=1)
    assert len(chunks) >= 2
    assert all(chunk.document_id == "DOC-1" for chunk in chunks)
    assert all(chunk.page_number == 1 for chunk in chunks)
    assert chunks[0].source_checksum == "checksum"
