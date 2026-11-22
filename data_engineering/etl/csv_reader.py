"""Strict CSV extraction with source-row tracking."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from data_engineering.etl.config import EXPECTED_COLUMNS


class CsvFormatError(ValueError):
    """Raised when a source CSV is missing, empty, or structurally malformed."""


def validate_csv(path: Path, dataset_name: str) -> list[str]:
    """Validate that a CSV exists and its header matches the dataset contract.

    Returns the header names.  Missing or unexpected columns are hard errors so
    fields cannot be silently dropped during ingestion.
    """
    if not path.is_file():
        raise CsvFormatError(f"{dataset_name}: expected file not found: {path.name}")

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise CsvFormatError(f"{dataset_name}: file is empty: {path.name}") from exc

    expected = EXPECTED_COLUMNS[dataset_name]
    if len(header) != len(set(header)):
        raise CsvFormatError(f"{dataset_name}: duplicate column names in {path.name}")
    missing = [name for name in expected if name not in header]
    unexpected = [name for name in header if name not in expected]
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected columns: {', '.join(unexpected)}")
        raise CsvFormatError(f"{dataset_name}: invalid header ({'; '.join(details)})")
    return header


def iter_rows(path: Path, dataset_name: str) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield ``(source_row_number, row)`` with row 1 being the header."""
    validate_csv(path, dataset_name)
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise CsvFormatError(
                    f"{dataset_name}: row {row_number} has more values than the header"
                )
            yield row_number, {
                key: ("" if value is None else str(value)) for key, value in row.items()
            }
