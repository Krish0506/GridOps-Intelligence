"""Document metadata extraction for the synthetic engineering corpus.

The source documents contain a small, machine-readable header.  Earlier
ingestion stored the filename as the title and a single ``Engineering``
category, which made category/equipment filtering ineffective.  Parsing the
header keeps the existing documents and chunks intact while exposing the
metadata that is actually present in the text.

The same header appears in three extraction layouts:

* plain text with one field per line;
* DOCX text with a human-readable title above the header;
* PDF text flattened onto a single line.

The extractor therefore anchors each field to its own label and bounds the
captured value, instead of treating everything after a label as its value.
"""

from __future__ import annotations

import re

TEXT_LIMIT = 6000

TITLE_PATTERN = re.compile(
    r"\bTitle\s*:\s*(?P<value>.{3,120}?)"
    r"(?=\s+(?:Document ID|Category|Revision|Equipment|Publication date)\s*:"
    r"|\s+(?:SYNTHETIC DEMONSTRATION DOCUMENT|Synthetic demonstration document)\b"
    r"|\.\s|$)",
    re.IGNORECASE | re.DOTALL,
)
CATEGORY_PATTERN = re.compile(
    r"\bCategory\s*:\s*(?P<value>[A-Za-z][A-Za-z &/-]{1,48}?)"
    r"(?=\s+(?:Document ID|Title|Revision|Equipment|Publication date|SYNTHETIC|Synthetic)\b|\.\s|$)",
    re.IGNORECASE | re.DOTALL,
)
REVISION_PATTERN = re.compile(
    r"\bRevision\s*:\s*(?P<value>Rev\s*[A-Za-z0-9.]+)", re.IGNORECASE
)
EQUIPMENT_PATTERN = re.compile(
    r"\bEquipment\s*:\s*(?P<value>[A-Za-z][A-Za-z_ ]{0,40}?)"
    r"(?=\s+(?:Document ID|Title|Category|Revision|Publication date|SYNTHETIC|Synthetic|The)\b|\.\s|$)",
    re.IGNORECASE | re.DOTALL,
)
PUBLICATION_PATTERN = re.compile(
    r"\bPublication date\s*:\s*(?P<value>\d{4}-\d{2}-\d{2})", re.IGNORECASE
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .;:\t\r\n")


def _search(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = _clean(match.group("value"))
    return value or None


def _normalize_equipment(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) > 64:
        return None
    equipment = value.lower().replace(" ", "_")
    equipment = re.sub(r"[^a-z_]", "", equipment)
    if not equipment:
        return None
    if equipment in {"all", "all_equipment", "any", "all_equipment_types"}:
        return "all"
    return equipment


def parse_document_metadata(text: str, fallback_id: str) -> dict[str, str | None]:
    """Parse the synthetic document header into normalized metadata."""
    header = text[:TEXT_LIMIT]

    title = _search(TITLE_PATTERN, header)
    if not title:
        # DOCX extraction puts the human title on the first non-empty line.
        for line in header.splitlines()[:8]:
            candidate = _clean(line)
            if (
                candidate
                and "synthetic demonstration" not in candidate.lower()
                and "document id" not in candidate.lower()
                and len(candidate) <= 120
            ):
                title = candidate
                break

    category = _search(CATEGORY_PATTERN, header) or "Engineering"
    revision = _search(REVISION_PATTERN, header)
    equipment = _normalize_equipment(_search(EQUIPMENT_PATTERN, header))
    publication_date = _search(PUBLICATION_PATTERN, header)

    return {
        "title": title or fallback_id,
        "category": category,
        "revision": revision or "Rev A",
        "equipment_applicability": equipment,
        "publication_date": publication_date,
    }


__all__ = ["parse_document_metadata"]
