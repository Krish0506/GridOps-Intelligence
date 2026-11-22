"""Shared helpers for the synthetic data generators and validators."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


def iso_ts(value: datetime) -> str:
    """Render a datetime as an ISO-8601 string."""
    return value.isoformat()


def parse_ts(value: str) -> datetime | None:
    """Parse an ISO-8601 string; return ``None`` for empty or invalid input."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def asset_id(asset: dict[str, str]) -> str:
    """Return the identifier of an asset row (its table-specific id column)."""
    from data_engineering.generators.config import ASSET_ID_FIELDS

    return str(asset[ASSET_ID_FIELDS[asset["asset_type"]]])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> Path:
    """Write rows to a CSV file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: ("" if row.get(name) is None else row[name]) for name in fieldnames})
    return path


def write_json(path: Path, data: dict) -> Path:
    """Write a JSON document with deterministic formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def load_rows(path: Path) -> list[dict[str, str]]:
    """Load every row of a CSV file as a dict of strings."""
    with path.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
