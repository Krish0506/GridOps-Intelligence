"""Text extraction from synthetic engineering documents."""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from pathlib import Path


def extract_text(path: Path) -> tuple[str, list[tuple[int, str]]]:
    """Extract text and per-page segments.

    Returns ``(full_text, pages)`` where ``pages`` is a list of
    ``(page_number, text)`` tuples (empty for non-paginated formats).
    """
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8")
        return text, [(1, text)]
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"unsupported document format: {suffix}")


def _extract_docx(path: Path) -> tuple[str, list[tuple[int, str]]]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    paragraphs = re.findall(r"<w:p[ >].*?</w:p>|<w:p/>", xml, re.DOTALL)
    texts: list[str] = []
    for paragraph in paragraphs:
        runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", paragraph, re.DOTALL)
        texts.append("".join(runs))
    joined = "\n".join(texts)
    return joined, [(1, joined)]


def _extract_pdf(path: Path) -> tuple[str, list[tuple[int, str]]]:
    data = path.read_bytes()
    # Collect text-showing operators from content streams.
    streams = _pdf_streams(data)
    page_texts: list[str] = []
    for stream in streams:
        page_texts.append(_text_from_content(stream))
    if not page_texts:
        page_texts = [_text_from_content(data.decode("latin-1", "replace"))]
    pages = [(index + 1, text) for index, text in enumerate(page_texts)]
    full = "\n".join(text for _, text in pages)
    return full, pages


def _pdf_streams(data: bytes) -> list[str]:
    streams: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.DOTALL):
        raw = match.group(1)
        try:
            decoded = zlib.decompress(raw)
        except zlib.error:
            decoded = raw
        streams.append(decoded.decode("latin-1", "replace"))
    return streams


def _text_from_content(content: str) -> str:
    pieces: list[str] = []
    for match in re.finditer(r"\((?:\\.|[^()\\])*\)\s*Tj", content):
        pieces.append(_unescape_pdf(match.group(0)))
    for match in re.finditer(r"\[(.*?)\]\s*TJ", content, re.DOTALL):
        for inner in re.finditer(r"\((?:\\.|[^()\\])*\)", match.group(1)):
            pieces.append(_unescape_pdf(inner.group(0)))
    return " ".join(pieces)


def _unescape_pdf(token: str) -> str:
    text = token
    if text.endswith("Tj") or text.endswith("TJ"):
        text = text[: text.rfind(")")]
    start = text.find("(")
    if start >= 0:
        text = text[start + 1 :]
    text = text.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
    text = text.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
    return text


__all__ = ["extract_text"]
