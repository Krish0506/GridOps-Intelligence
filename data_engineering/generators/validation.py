"""Validation for synthetic data files.

Checks: missing required fields, invalid identifiers, duplicate records,
invalid timestamps, invalid numeric ranges, broken asset references,
unexpected categories, and data completeness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from data_engineering.generators.base import load_rows, parse_ts
from data_engineering.generators.config import (
    ASSET_CATEGORY_FIELDS,
    ASSET_ID_FIELDS,
    ASSET_RANGES,
    ASSET_REQUIRED_FIELDS,
    ASSET_STATUS_VALUES,
    ASSET_TABLES,
    ASSET_TIMESTAMP_FIELDS,
    COMPLETENESS_MIN,
    FAILURE_CATEGORIES,
    FAILURE_RANGES,
    FAILURE_REQUIRED_FIELDS,
    ID_PATTERNS,
    INSPECTION_CONDITIONS,
    INSPECTION_REQUIRED_FIELDS,
    INSPECTION_SEVERITIES,
    OUTPUT_DIR,
    PRIORITIES,
    REFERENCE_DATE,
    TELEMETRY_RANGES,
    TELEMETRY_REQUIRED_FIELDS,
    WEATHER_RANGES,
    WEATHER_REQUIRED_FIELDS,
    WORK_ORDER_REQUIRED_FIELDS,
    WORK_STATUSES,
    WORK_TYPES,
)

MAX_TS_BOUND = REFERENCE_DATE + timedelta(days=1)


@dataclass
class Issue:
    """A single validation finding."""

    severity: str  # "error" | "missing" | "duplicate"
    table: str
    message: str
    row_index: int | None = None
    field: str | None = None

    def describe(self) -> str:
        location = f"row {self.row_index}" if self.row_index is not None else ""
        field = f" field '{self.field}'" if self.field else ""
        return f"[{self.table}] {self.severity}: {self.message} ({location}{field})".strip()


@dataclass
class TableResult:
    """Validation result for one table."""

    table: str
    row_count: int = 0
    completeness: float = 1.0
    errors: list[Issue] = field(default_factory=list)
    missing_fields: list[Issue] = field(default_factory=list)
    duplicates: list[Issue] = field(default_factory=list)

    @property
    def issues(self) -> list[Issue]:
        return self.errors + self.missing_fields + self.duplicates

    @property
    def ok(self) -> bool:
        return not self.errors


def _completeness(affected: set[int], rows: list) -> float:
    if not rows:
        return 1.0
    return 1.0 - len(affected) / len(rows)


def _append_completeness_error(issues: list[Issue], table: str, completeness: float) -> None:
    if completeness < COMPLETENESS_MIN:
        issues.append(
            Issue(
                "error",
                table,
                f"data completeness {completeness:.1%} is below the minimum {COMPLETENESS_MIN:.0%}",
            )
        )


# ---------------------------------------------------------------------------
# Generic checkers.
def check_synthetic(rows: list[dict], table: str) -> list[Issue]:
    """Every row must be marked as synthetic."""
    return [
        Issue("error", table, "row missing synthetic marker (expected 'true')", i, "synthetic")
        for i, row in enumerate(rows)
        if str(row.get("synthetic", "") or "").strip() != "true"
    ]


def check_required_fields(rows: list[dict], required: list[str], table: str) -> tuple[list[Issue], set[int]]:
    """Flag rows with any empty required field; return (issues, affected row indices)."""
    issues: list[Issue] = []
    affected: set[int] = set()
    for i, row in enumerate(rows):
        for name in required:
            if not str(row.get(name, "") or "").strip():
                issues.append(Issue("missing", table, f"required field '{name}' is empty", i, name))
                affected.add(i)
    return issues, affected


def check_identifiers(rows: list[dict], id_field: str, table: str) -> tuple[list[Issue], list[Issue]]:
    """Validate identifier format and uniqueness per table."""
    errors: list[Issue] = []
    duplicates: list[Issue] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        value = str(row.get(id_field, "") or "").strip()
        if not value:
            errors.append(Issue("error", table, f"'{id_field}' is empty", i, id_field))
            continue
        if re.fullmatch(ID_PATTERNS[table], value) is None:
            errors.append(Issue("error", table, f"invalid identifier '{value}'", i, id_field))
        if value in seen:
            duplicates.append(Issue("duplicate", table, f"duplicate identifier '{value}'", i, id_field))
        else:
            seen.add(value)
    return errors, duplicates


def check_timestamps(
    rows: list[dict], fields: list[str], table: str, max_date: datetime = MAX_TS_BOUND
) -> list[Issue]:
    """Validate that timestamp fields parse as ISO-8601 and are not in the future."""
    errors: list[Issue] = []
    for i, row in enumerate(rows):
        for name in fields:
            value = str(row.get(name, "") or "").strip()
            if not value:
                continue
            ts = parse_ts(value)
            if ts is None:
                errors.append(Issue("error", table, f"invalid timestamp '{value}'", i, name))
            elif ts > max_date:
                errors.append(
                    Issue(
                        "error",
                        table,
                        f"timestamp '{value}' is after the reference date {max_date.date()}",
                        i,
                        name,
                    )
                )
    return errors


def check_numeric_ranges(rows: list[dict], ranges: dict[str, tuple[float, float]], table: str) -> list[Issue]:
    """Validate that numeric fields parse and fall within inclusive ranges."""
    errors: list[Issue] = []
    for i, row in enumerate(rows):
        for name, (lo, hi) in ranges.items():
            raw = str(row.get(name, "") or "").strip()
            if raw == "":
                continue
            try:
                value = float(raw)
            except ValueError:
                errors.append(Issue("error", table, f"non-numeric value '{raw}' in field '{name}'", i, name))
                continue
            if not (lo <= value <= hi):
                errors.append(
                    Issue("error", table, f"field '{name}' value {raw} out of range [{lo}, {hi}]", i, name)
                )
    return errors


def check_categories(rows: list[dict], field: str, allowed, table: str) -> list[Issue]:
    """Validate that categorical values are from the expected vocabulary."""
    errors: list[Issue] = []
    for i, row in enumerate(rows):
        value = str(row.get(field, "") or "").strip()
        if value and value not in allowed:
            errors.append(Issue("error", table, f"unexpected category '{value}' in field '{field}'", i, field))
    return errors


def check_asset_references(rows: list[dict], asset_index: set[str], field: str, table: str) -> list[Issue]:
    """Validate foreign-key-style references to asset ids."""
    errors: list[Issue] = []
    for i, row in enumerate(rows):
        value = str(row.get(field, "") or "").strip()
        if not value:
            errors.append(Issue("error", table, f"'{field}' is empty", i, field))
        elif value not in asset_index:
            errors.append(Issue("error", table, f"broken asset reference '{value}'", i, field))
    return errors


def check_duplicates(rows: list[dict], table: str) -> list[Issue]:
    """Detect exact duplicate records."""
    seen: set[tuple] = set()
    duplicates: list[Issue] = []
    for i, row in enumerate(rows):
        key = tuple(sorted((k, str(v or "")) for k, v in row.items()))
        if key in seen:
            duplicates.append(Issue("duplicate", table, f"duplicate record (row {i})", i))
        else:
            seen.add(key)
    return duplicates


def check_work_order_dates(rows: list[dict], table: str) -> list[Issue]:
    """Validate opened/completed timestamp ordering for work orders."""
    errors: list[Issue] = []
    for i, row in enumerate(rows):
        opened_raw = str(row.get("opened_at", "") or "").strip()
        completed_raw = str(row.get("completed_at", "") or "").strip()
        opened = parse_ts(opened_raw)
        if opened is None and completed_raw:
            errors.append(
                Issue("error", table, "invalid or missing 'opened_at' while 'completed_at' is set", i, "opened_at")
            )
        if opened is not None and completed_raw:
            completed = parse_ts(completed_raw)
            if completed is None:
                errors.append(
                    Issue("error", table, f"invalid timestamp '{completed_raw}' in field 'completed_at'", i, "completed_at")
                )
            elif completed < opened:
                errors.append(
                    Issue(
                        "error",
                        table,
                        f"completed_at '{completed_raw}' precedes opened_at '{opened_raw}'",
                        i,
                        "completed_at",
                    )
                )
    return errors


def check_completed_required(rows: list[dict], table: str) -> list[Issue]:
    """Flag completed work orders whose completed_at is missing."""
    issues: list[Issue] = []
    for i, row in enumerate(rows):
        status = str(row.get("status", "") or "").strip()
        completed_at = str(row.get("completed_at", "") or "").strip()
        if status == "completed" and not completed_at:
            issues.append(
                Issue(
                    "missing",
                    table,
                    "required field 'completed_at' is empty (status is 'completed')",
                    i,
                    "completed_at",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Per-table validation.
def _validate_asset_table(table: str, rows: list[dict]) -> TableResult:
    id_field = ASSET_ID_FIELDS[table]
    required = [id_field, "synthetic"] + ASSET_REQUIRED_FIELDS[table]
    missing_fields, affected = check_required_fields(rows, required, table)
    errors = list(check_synthetic(rows, table))
    errors += check_identifiers(rows, id_field, table)[0]
    errors += check_timestamps(rows, ASSET_TIMESTAMP_FIELDS[table], table)
    errors += check_numeric_ranges(rows, ASSET_RANGES[table], table)
    errors += check_categories(rows, "status", ASSET_STATUS_VALUES, table)
    category_field = ASSET_CATEGORY_FIELDS.get(table)
    if category_field is not None:
        errors += check_categories(rows, category_field[0], category_field[1], table)
    completeness = _completeness(affected, rows)
    _append_completeness_error(errors, table, completeness)
    if not rows:
        errors.append(Issue("error", table, "table is empty"))
    return TableResult(
        table=table,
        row_count=len(rows),
        completeness=completeness,
        errors=errors,
        missing_fields=missing_fields,
        duplicates=check_identifiers(rows, id_field, table)[1],
    )


def _validate_telemetry(
    rows: list[dict], asset_index: set[str], asset_type_by_id: dict[str, str]
) -> TableResult:
    table = "asset_telemetry"
    required = ["synthetic"] + TELEMETRY_REQUIRED_FIELDS
    missing_fields, affected = check_required_fields(rows, required, table)
    errors = list(check_synthetic(rows, table))
    errors += check_asset_references(rows, asset_index, "asset_id", table)
    for i, row in enumerate(rows):
        asset_id = str(row.get("asset_id", "") or "").strip()
        asset_type = str(row.get("asset_type", "") or "").strip()
        expected = asset_type_by_id.get(asset_id)
        if expected is not None and asset_type != expected:
            errors.append(
                Issue(
                    "error",
                    table,
                    f"asset_type '{asset_type}' does not match the asset table '{expected}' for asset '{asset_id}'",
                    i,
                    "asset_type",
                )
            )
    errors += check_categories(rows, "asset_type", set(ASSET_TABLES), table)
    errors += check_timestamps(rows, ["timestamp"], table)
    errors += check_numeric_ranges(rows, TELEMETRY_RANGES, table)
    completeness = _completeness(affected, rows)
    _append_completeness_error(errors, table, completeness)
    if not rows:
        errors.append(Issue("error", table, "table is empty"))
    return TableResult(
        table=table,
        row_count=len(rows),
        completeness=completeness,
        errors=errors,
        missing_fields=missing_fields,
        duplicates=check_duplicates(rows, table),
    )


def _validate_work_orders(rows: list[dict], asset_index: set[str]) -> TableResult:
    table = "work_orders"
    required = ["work_order_id", "synthetic"] + WORK_ORDER_REQUIRED_FIELDS
    missing_fields, affected = check_required_fields(rows, required, table)
    errors = list(check_synthetic(rows, table))
    errors += check_asset_references(rows, asset_index, "asset_ref", table)
    errors += check_categories(rows, "work_type", set(WORK_TYPES), table)
    errors += check_categories(rows, "priority", set(PRIORITIES), table)
    errors += check_categories(rows, "status", set(WORK_STATUSES), table)
    errors += check_timestamps(rows, ["opened_at", "completed_at"], table)
    errors += check_work_order_dates(rows, table)
    missing_fields += check_completed_required(rows, table)
    completeness = _completeness(affected, rows)
    _append_completeness_error(errors, table, completeness)
    if not rows:
        errors.append(Issue("error", table, "table is empty"))
    return TableResult(
        table=table,
        row_count=len(rows),
        completeness=completeness,
        errors=errors,
        missing_fields=missing_fields,
        duplicates=check_duplicates(rows, table),
    )


def _validate_inspections(rows: list[dict], asset_index: set[str]) -> TableResult:
    table = "inspections"
    missing_fields, affected = check_required_fields(rows, ["synthetic"] + INSPECTION_REQUIRED_FIELDS, table)
    errors = list(check_synthetic(rows, table))
    errors += check_asset_references(rows, asset_index, "asset_ref", table)
    errors += check_categories(rows, "condition", set(INSPECTION_CONDITIONS), table)
    errors += check_categories(rows, "severity", set(INSPECTION_SEVERITIES), table)
    errors += check_timestamps(rows, ["inspection_date"], table)
    completeness = _completeness(affected, rows)
    _append_completeness_error(errors, table, completeness)
    if not rows:
        errors.append(Issue("error", table, "table is empty"))
    return TableResult(
        table=table,
        row_count=len(rows),
        completeness=completeness,
        errors=errors,
        missing_fields=missing_fields,
        duplicates=check_duplicates(rows, table),
    )


def _validate_failures(rows: list[dict], asset_index: set[str]) -> TableResult:
    table = "failures"
    missing_fields, affected = check_required_fields(rows, ["failure_id", "synthetic"] + FAILURE_REQUIRED_FIELDS, table)
    errors = list(check_synthetic(rows, table))
    errors += check_asset_references(rows, asset_index, "asset_ref", table)
    errors += check_categories(rows, "failure_category", set(FAILURE_CATEGORIES), table)
    errors += check_timestamps(rows, ["failure_timestamp"], table)
    errors += check_numeric_ranges(rows, FAILURE_RANGES, table)
    completeness = _completeness(affected, rows)
    _append_completeness_error(errors, table, completeness)
    if not rows:
        errors.append(Issue("error", table, "table is empty"))
    return TableResult(
        table=table,
        row_count=len(rows),
        completeness=completeness,
        errors=errors,
        missing_fields=missing_fields,
        duplicates=check_duplicates(rows, table),
    )


def _validate_weather(rows: list[dict]) -> TableResult:
    table = "weather"
    missing_fields, affected = check_required_fields(rows, ["synthetic"] + WEATHER_REQUIRED_FIELDS, table)
    errors = list(check_synthetic(rows, table))
    errors += check_categories(rows, "severe", {"true", "false"}, table)
    errors += check_timestamps(rows, ["timestamp"], table)
    errors += check_numeric_ranges(rows, WEATHER_RANGES, table)
    completeness = _completeness(affected, rows)
    _append_completeness_error(errors, table, completeness)
    if not rows:
        errors.append(Issue("error", table, "table is empty"))
    return TableResult(
        table=table,
        row_count=len(rows),
        completeness=completeness,
        errors=errors,
        missing_fields=missing_fields,
        duplicates=check_duplicates(rows, table),
    )


def validate_all(output_dir: Path | str | None = None) -> dict[str, TableResult]:
    """Validate every synthetic dataset in ``output_dir``.

    Returns a mapping of table name to ``TableResult``. A table ``ok`` when
    it has no hard errors; ``missing_fields`` and ``duplicates`` are recorded
    separately (duplicates are intentional for data-quality tests).
    """
    output_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR

    asset_index: set[str] = set()
    asset_type_by_id: dict[str, str] = {}
    asset_rows: dict[str, list[dict]] = {}
    for table in ASSET_TABLES:
        id_field = ASSET_ID_FIELDS[table]
        rows = load_rows(output_dir / f"{table}.csv")
        asset_rows[table] = rows
        for row in rows:
            asset_id = str(row.get(id_field, "") or "").strip()
            if asset_id:
                asset_index.add(asset_id)
                asset_type_by_id.setdefault(asset_id, table)

    results: dict[str, TableResult] = {
        table: _validate_asset_table(table, asset_rows[table]) for table in ASSET_TABLES
    }
    results["asset_telemetry"] = _validate_telemetry(
        load_rows(output_dir / "asset_telemetry.csv"), asset_index, asset_type_by_id
    )
    results["work_orders"] = _validate_work_orders(load_rows(output_dir / "work_orders.csv"), asset_index)
    results["inspections"] = _validate_inspections(load_rows(output_dir / "inspections.csv"), asset_index)
    results["failures"] = _validate_failures(load_rows(output_dir / "failures.csv"), asset_index)
    results["weather"] = _validate_weather(load_rows(output_dir / "weather.csv"))
    return results
