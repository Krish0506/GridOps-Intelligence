"""Structured ingestion and rejected-row report writers."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _write_atomic(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, default=_json_default),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def write_ingestion_report(report: dict[str, Any], report_dir: Path) -> Path:
    """Write the structured JSON report for one run."""
    return _write_atomic(report_dir / f"{report['run_id']}.json", report)


def write_rejected_rows(
    run_id: str, rejected: list[dict[str, Any]], rejected_dir: Path
) -> Path:
    """Write rejected rows with source file, row number, and reason."""
    return _write_atomic(
        rejected_dir / f"{run_id}.json",
        {
            "run_id": run_id,
            "rejected_count": len(rejected),
            "records": rejected,
        },
    )
