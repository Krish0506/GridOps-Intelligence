"""Synthetic engineering document corpus generator (Milestone 4)."""

from __future__ import annotations

import argparse
import hashlib
import random
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "knowledge_base" / "source_documents"

DOCUMENTS: list[dict[str, str]] = [
    {
        "document_id": "DOC-TX-001",
        "title": "Transformer Maintenance Procedure",
        "category": "Maintenance",
        "revision": "Rev A",
        "equipment": "transformers",
        "body": (
            "Synthetic demonstration document. Inspect transformer bushings, cooling fans, "
            "and oil level. Elevated temperature or vibration may indicate developing faults. "
            "Follow scheduled preventive maintenance intervals."
        ),
    },
    {
        "document_id": "DOC-TX-002",
        "title": "Transformer Insulation Degradation",
        "category": "Condition Assessment",
        "revision": "Rev A",
        "equipment": "transformers",
        "body": (
            "Synthetic demonstration document. Insulation resistance trending and thermal "
            "imaging help identify insulation deterioration. Compare readings to baseline."
        ),
    },
    {
        "document_id": "DOC-TX-003",
        "title": "Transformer Oil Analysis Guidance",
        "category": "Diagnostics",
        "revision": "Rev B",
        "equipment": "transformers",
        "body": (
            "Synthetic demonstration document. Dissolved gas analysis can indicate overheating "
            "or partial discharge. Results require engineering review."
        ),
    },
    {
        "document_id": "DOC-SUB-001",
        "title": "Substation Inspection Procedure",
        "category": "Inspection",
        "revision": "Rev A",
        "equipment": "substations",
        "body": (
            "Synthetic demonstration document. Inspect bus connections, breakers, and "
            "switchgear. Look for corrosion, overheating, and abnormal noise."
        ),
    },
    {
        "document_id": "DOC-CB-001",
        "title": "Circuit Breaker Maintenance",
        "category": "Maintenance",
        "revision": "Rev A",
        "equipment": "circuit_breakers",
        "body": (
            "Synthetic demonstration document. Verify trip coils, contact wear, and "
            "operating times. Abnormal vibration may indicate mechanical wear."
        ),
    },
    {
        "document_id": "DOC-FD-001",
        "title": "Feeder Reliability Guide",
        "category": "Reliability",
        "revision": "Rev A",
        "equipment": "feeders",
        "body": (
            "Synthetic demonstration document. Monitor feeder overcurrent events and "
            "reclosure activity. Elevated vibration or temperature may precede failures."
        ),
    },
    {
        "document_id": "DOC-TH-001",
        "title": "Thermal Inspection Procedure",
        "category": "Inspection",
        "revision": "Rev A",
        "equipment": "all",
        "body": (
            "Synthetic demonstration document. Thermal imaging identifies hot spots on "
            "electrical equipment. Compare thermal patterns to historical baselines."
        ),
    },
    {
        "document_id": "DOC-PM-001",
        "title": "Preventive Maintenance Schedule",
        "category": "Maintenance",
        "revision": "Rev A",
        "equipment": "all",
        "body": (
            "Synthetic demonstration document. Preventive maintenance intervals depend on "
            "asset condition, operating hours, and environmental stress."
        ),
    },
    {
        "document_id": "DOC-CA-001",
        "title": "Asset Condition Assessment",
        "category": "Condition Assessment",
        "revision": "Rev A",
        "equipment": "all",
        "body": (
            "Synthetic demonstration document. Condition assessment combines telemetry, "
            "inspection findings, and maintenance history."
        ),
    },
    {
        "document_id": "DOC-FI-001",
        "title": "Failure Indicators",
        "category": "Diagnostics",
        "revision": "Rev A",
        "equipment": "all",
        "body": (
            "Synthetic demonstration document. Rising temperature, vibration, and load "
            "may indicate impending failures. Interpret alongside maintenance records."
        ),
    },
    {
        "document_id": "DOC-WX-001",
        "title": "Weather-Related Asset Stress",
        "category": "Environmental",
        "revision": "Rev A",
        "equipment": "all",
        "body": (
            "Synthetic demonstration document. Severe weather can stress electrical assets. "
            "Monitor weather-correlated anomalies."
        ),
    },
    {
        "document_id": "DOC-TS-001",
        "title": "Engineering Troubleshooting Guidance",
        "category": "Troubleshooting",
        "revision": "Rev A",
        "equipment": "all",
        "body": (
            "Synthetic demonstration document. When anomalies are detected, verify sensor "
            "calibration and inspect recent maintenance activity."
        ),
    },
]


def _write_txt(path: Path, doc: dict[str, str]) -> None:
    content = (
        f"SYNTHETIC DEMONSTRATION DOCUMENT\n"
        f"Document ID: {doc['document_id']}\n"
        f"Title: {doc['title']}\n"
        f"Category: {doc['category']}\n"
        f"Revision: {doc['revision']}\n"
        f"Equipment: {doc['equipment']}\n"
        f"Publication date: 2026-01-01\n\n"
        f"{doc['body']}\n"
    )
    path.write_text(content, encoding="utf-8")


def _write_docx(path: Path, doc: dict[str, str]) -> None:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        f"<w:p><w:r><w:t>{escape(doc['title'])}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>Document ID: {escape(doc['document_id'])}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>Category: {escape(doc['category'])}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>Revision: {escape(doc['revision'])}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>Equipment: {escape(doc['equipment'])}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>{escape(doc['body'])}</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )


def _write_pdf(path: Path, doc: dict[str, str]) -> None:
    lines = [
        "SYNTHETIC DEMONSTRATION DOCUMENT",
        f"Document ID: {doc['document_id']}",
        f"Title: {doc['title']}",
        f"Category: {doc['category']}",
        f"Revision: {doc['revision']}",
        f"Equipment: {doc['equipment']}",
        doc["body"],
    ]
    content_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({line}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", "replace")
    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        b"5 0 obj\n<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream\nendobj\n"
    )
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_offset = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
    path.write_bytes(pdf)


def generate_corpus(output_dir: Path) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    for document in DOCUMENTS:
        for extension, writer in (("txt", _write_txt), ("docx", _write_docx), ("pdf", _write_pdf)):
            filename = f"{document['document_id']}.{extension}"
            path = output_dir / filename
            writer(path, document)
            manifest.append(
                {
                    "document_id": document["document_id"],
                    "title": document["title"],
                    "category": document["category"],
                    "revision": document["revision"],
                    "equipment": document["equipment"],
                    "format": extension,
                    "filename": filename,
                    "checksum": _sha256(path),
                }
            )
    (output_dir / "manifest.json").write_text(
        __import__("json").dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic engineering document corpus.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    manifest = generate_corpus(args.output)
    print(f"Generated {len(manifest)} documents in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
