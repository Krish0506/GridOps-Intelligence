"""Row-level validation and data-quality accounting for the ETL.

Validation never mutates source rows.  Errors reject a row; warnings preserve
the row (for example, a missing telemetry sensor reading) and are recorded for
reporting.  Every check is counted so results can be persisted in
``data_quality_results``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from data_engineering.generators.base import parse_ts
from data_engineering.generators.config import (
    ASSET_CATEGORY_FIELDS,
    ASSET_RANGES,
    ASSET_REQUIRED_FIELDS,
    ASSET_STATUSES,
    ASSET_TIMESTAMP_FIELDS,
    CATEGORY_BY_ASSET_TYPE,
    FAILURE_CATEGORIES,
    FAILURE_RANGES,
    FAILURE_REQUIRED_FIELDS,
    ID_PATTERNS,
    INSPECTION_CONDITIONS,
    INSPECTION_REQUIRED_FIELDS,
    INSPECTION_SEVERITIES,
    PRIORITIES,
    REFERENCE_DATE,
    REGIONS,
    TELEMETRY_RANGES,
    WEATHER_RANGES,
    WEATHER_REQUIRED_FIELDS,
    WORK_ORDER_REQUIRED_FIELDS,
    WORK_STATUSES,
    WORK_TYPES,
)
from data_engineering.etl.config import ASSET_DATASETS, DATASET_ID_FIELDS

MAX_TS_BOUND = REFERENCE_DATE + timedelta(days=1)

# Sensor readings that the generator intentionally leaves empty.
TELEMETRY_OPTIONAL_SENSORS = ("temperature_c", "load_pct", "current_a", "vibration_mm_s")

TELEMETRY_REQUIRED = [
    "asset_id",
    "asset_type",
    "timestamp",
    "voltage_kv",
    "operating_hours_cumulative",
    "synthetic",
]

CHECK_SEVERITY = {
    "asset_id_uniqueness": "WARNING",
    "valid_asset_types": "ERROR",
    "valid_asset_references": "ERROR",
    "required_field_completeness": "ERROR",
    "identifier_format": "ERROR",
    "timestamp_format": "ERROR",
    "numeric_ranges": "ERROR",
    "category_values": "ERROR",
    "work_order_status_transitions": "ERROR",
    "completed_at_order": "ERROR",
    "failure_severity": "ERROR",
    "telemetry_completeness": "WARNING",
    "duplicate_detection": "WARNING",
    "synthetic_marker_presence": "ERROR",
}


@dataclass(frozen=True)
class Issue:
    """One validation finding tied to a source row."""

    dataset: str
    source_row: int
    identifier: str | None
    check: str
    severity: str
    field: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "source_row": self.source_row,
            "identifier": self.identifier,
            "check": self.check,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
        }


@dataclass
class CheckStats:
    """Accumulated counts for one named check on one dataset."""

    check_name: str
    severity: str
    checked: int = 0
    passed: int = 0
    failed: int = 0
    samples: Counter[str] = field(default_factory=Counter)

    def add(self, checked: int, failed: int, detail: str | None = None) -> None:
        self.checked += checked
        self.failed += failed
        self.passed += max(0, checked - failed)
        if failed and detail:
            self.samples[detail] += 1

    def to_dict(self) -> dict[str, Any]:
        rate = (self.failed / self.checked) if self.checked else 0.0
        return {
            "check_name": self.check_name,
            "severity": self.severity,
            "records_checked": self.checked,
            "records_passed": self.passed,
            "records_failed": self.failed,
            "failure_rate": round(rate, 6),
            "samples": [message for message, _ in self.samples.most_common(5)],
        }


class QualityTracker:
    """Collects per-check pass/fail counts for one dataset."""

    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        self._stats: dict[str, CheckStats] = {}

    def record(
        self,
        check: str,
        *,
        checked: int = 1,
        failed: int = 0,
        detail: str | None = None,
        severity: str | None = None,
    ) -> None:
        stat = self._stats.get(check)
        if stat is None:
            stat = CheckStats(check, severity or CHECK_SEVERITY.get(check, "INFO"))
            self._stats[check] = stat
        stat.add(checked, failed, detail)

    def results(self) -> list[dict[str, Any]]:
        return [self._stats[name].to_dict() for name in sorted(self._stats)]

    def summary(self) -> dict[str, Any]:
        total_failed = sum(stat.failed for stat in self._stats.values())
        total_checked = sum(stat.checked for stat in self._stats.values())
        return {
            "checks": len(self._stats),
            "records_checked": total_checked,
            "records_failed": total_failed,
            "failure_rate": round(total_failed / total_checked, 6) if total_checked else 0.0,
        }


def row_fingerprint(row: dict[str, str]) -> str:
    """Stable SHA-256 digest of the normalized source row."""
    canonical = json.dumps(
        {key: str(value or "").strip() for key, value in sorted(row.items())},
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DuplicateTracker:
    """Detects exact duplicates and conflicting duplicate identifiers."""

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}
        self.exact = 0
        self.conflicts = 0

    def classify(self, key: str, fingerprint: str) -> str:
        """Return ``new``, ``exact``, or ``conflict``."""
        previous = self._seen.get(key)
        if previous is None:
            self._seen[key] = fingerprint
            return "new"
        if previous == fingerprint:
            self.exact += 1
            return "exact"
        self.conflicts += 1
        return "conflict"


def _text(row: dict[str, str], field_name: str) -> str:
    return str(row.get(field_name, "") or "").strip()


def _parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _asset_type(row: dict[str, str]) -> str:
    return _text(row, "asset_type")


class RowValidator:
    """Validates one dataset row and updates the quality tracker."""

    def __init__(
        self,
        dataset: str,
        asset_types: dict[str, str],
        substation_ids: set[str],
        tracker: QualityTracker,
    ) -> None:
        self.dataset = dataset
        self.asset_types = asset_types
        self.substation_ids = substation_ids
        self.tracker = tracker

    def validate(self, row: dict[str, str], source_row: int) -> list[Issue]:
        """Return all issues for one row.  Any ERROR issue rejects the row."""
        if self.dataset in ASSET_DATASETS:
            return self._validate_asset(row, source_row)
        if self.dataset == "asset_telemetry":
            return self._validate_telemetry(row, source_row)
        if self.dataset == "work_orders":
            return self._validate_work_order(row, source_row)
        if self.dataset == "inspections":
            return self._validate_inspection(row, source_row)
        if self.dataset == "failures":
            return self._validate_failure(row, source_row)
        if self.dataset == "weather":
            return self._validate_weather(row, source_row)
        raise ValueError(f"Unknown dataset: {self.dataset}")

    # ------------------------------------------------------------------
    # Shared helpers.
    def _issue(
        self,
        source_row: int,
        identifier: str | None,
        check: str,
        severity: str,
        field_name: str | None,
        message: str,
    ) -> Issue:
        return Issue(
            dataset=self.dataset,
            source_row=source_row,
            identifier=identifier,
            check=check,
            severity=severity,
            field=field_name,
            message=message,
        )

    def _required(
        self, row: dict[str, str], required: list[str], source_row: int, identifier: str | None
    ) -> list[Issue]:
        issues = []
        missing = [name for name in required if not _text(row, name)]
        for name in missing:
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "required_field_completeness",
                    "ERROR",
                    name,
                    f"required field '{name}' is empty",
                )
            )
        self.tracker.record(
            "required_field_completeness",
            failed=1 if missing else 0,
            detail=f"missing: {', '.join(missing)}" if missing else None,
        )
        return issues

    def _identifier(
        self, value: str, source_row: int, field_name: str
    ) -> list[Issue]:
        pattern = ID_PATTERNS.get(self.dataset)
        if pattern is None or re.fullmatch(pattern, value):
            self.tracker.record("identifier_format", failed=0)
            return []
        self.tracker.record(
            "identifier_format", failed=1, detail=f"invalid identifier '{value}'"
        )
        return [
            self._issue(
                source_row,
                value,
                "identifier_format",
                "ERROR",
                field_name,
                f"invalid identifier '{value}' for {self.dataset}",
            )
        ]

    def _timestamps(
        self, row: dict[str, str], fields: list[str], source_row: int, identifier: str | None
    ) -> list[Issue]:
        issues = []
        for name in fields:
            raw = _text(row, name)
            if not raw:
                continue
            parsed = parse_ts(raw)
            if parsed is None:
                issues.append(
                    self._issue(
                        source_row,
                        identifier,
                        "timestamp_format",
                        "ERROR",
                        name,
                        f"invalid timestamp '{raw}' in '{name}'",
                    )
                )
            elif parsed > MAX_TS_BOUND:
                issues.append(
                    self._issue(
                        source_row,
                        identifier,
                        "timestamp_format",
                        "ERROR",
                        name,
                        f"timestamp '{raw}' is after the reference date",
                    )
                )
        self.tracker.record(
            "timestamp_format",
            failed=1 if issues else 0,
            detail=issues[0].message if issues else None,
        )
        return issues

    def _numbers(
        self,
        row: dict[str, str],
        ranges: dict[str, tuple[float, float]],
        source_row: int,
        identifier: str | None,
    ) -> list[Issue]:
        issues = []
        for name, (low, high) in ranges.items():
            raw = _text(row, name)
            if raw == "":
                # Empty required fields are reported by required_field_completeness.
                continue
            try:
                value = float(raw)
            except ValueError:
                issues.append(
                    self._issue(
                        source_row,
                        identifier,
                        "numeric_ranges",
                        "ERROR",
                        name,
                        f"non-numeric value '{raw}' in '{name}'",
                    )
                )
                continue
            if not (low <= value <= high):
                issues.append(
                    self._issue(
                        source_row,
                        identifier,
                        "numeric_ranges",
                        "ERROR",
                        name,
                        f"'{name}' value {raw} outside [{low}, {high}]",
                    )
                )
        numeric_issues = [issue for issue in issues if issue.check == "numeric_ranges"]
        self.tracker.record(
            "numeric_ranges",
            failed=1 if numeric_issues else 0,
            detail=numeric_issues[0].message if numeric_issues else None,
        )
        return issues

    def _category(
        self,
        value: str,
        allowed: set[str] | list[str],
        field_name: str,
        source_row: int,
        identifier: str | None,
        *,
        check: str = "category_values",
    ) -> list[Issue]:
        if value and value not in set(allowed):
            self.tracker.record(check, failed=1, detail=f"{field_name}='{value}'")
            return [
                self._issue(
                    source_row,
                    identifier,
                    check,
                    "ERROR",
                    field_name,
                    f"unexpected value '{value}' in '{field_name}'",
                )
            ]
        self.tracker.record(check, failed=0)
        return []

    def _synthetic(
        self, row: dict[str, str], source_row: int, identifier: str | None
    ) -> list[Issue]:
        value = _parse_bool(_text(row, "synthetic"))
        if value is True:
            self.tracker.record("synthetic_marker_presence", failed=0)
            return []
        self.tracker.record(
            "synthetic_marker_presence", failed=1, detail="missing or false synthetic marker"
        )
        return [
            self._issue(
                source_row,
                identifier,
                "synthetic_marker_presence",
                "ERROR",
                "synthetic",
                "row is not marked synthetic='true'",
            )
        ]

    def _asset_reference(
        self,
        reference: str,
        source_row: int,
        field_name: str,
        identifier: str | None,
        *,
        expected_type: str | None = None,
    ) -> list[Issue]:
        if not reference:
            self.tracker.record("valid_asset_references", failed=1, detail="empty reference")
            return [
                self._issue(
                    source_row,
                    identifier,
                    "valid_asset_references",
                    "ERROR",
                    field_name,
                    f"'{field_name}' is empty",
                )
            ]
        actual_type = self.asset_types.get(reference)
        if actual_type is None:
            self.tracker.record(
                "valid_asset_references", failed=1, detail=f"missing asset {reference}"
            )
            return [
                self._issue(
                    source_row,
                    identifier,
                    "valid_asset_references",
                    "ERROR",
                    field_name,
                    f"broken asset reference '{reference}'",
                )
            ]
        if expected_type is not None and actual_type != expected_type:
            self.tracker.record(
                "valid_asset_references",
                failed=1,
                detail=f"{reference} is {actual_type}, expected {expected_type}",
            )
            return [
                self._issue(
                    source_row,
                    identifier,
                    "valid_asset_references",
                    "ERROR",
                    field_name,
                    f"asset '{reference}' is type '{actual_type}', expected '{expected_type}'",
                )
            ]
        self.tracker.record("valid_asset_references", failed=0)
        return []

    # ------------------------------------------------------------------
    # Dataset-specific validation.
    def _validate_asset(self, row: dict[str, str], source_row: int) -> list[Issue]:
        id_field = DATASET_ID_FIELDS[self.dataset]
        identifier = _text(row, id_field)
        required = [id_field, "asset_type", "synthetic"] + ASSET_REQUIRED_FIELDS[self.dataset]
        issues = self._required(row, required, source_row, identifier)
        issues += self._identifier(identifier, source_row, id_field)
        issues += self._timestamps(
            row, ASSET_TIMESTAMP_FIELDS[self.dataset], source_row, identifier
        )
        issues += self._numbers(
            row, ASSET_RANGES[self.dataset], source_row, identifier
        )
        issues += self._category(
            _text(row, "status"), ASSET_STATUSES, "status", source_row, identifier
        )
        category_field = ASSET_CATEGORY_FIELDS.get(self.dataset)
        if category_field is not None:
            issues += self._category(
                _text(row, category_field[0]),
                category_field[1],
                category_field[0],
                source_row,
                identifier,
            )
        asset_type = _asset_type(row)
        if asset_type and asset_type != self.dataset:
            self.tracker.record("valid_asset_types", failed=1, detail=asset_type)
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "valid_asset_types",
                    "ERROR",
                    "asset_type",
                    f"asset_type '{asset_type}' does not match dataset '{self.dataset}'",
                )
            )
        else:
            self.tracker.record("valid_asset_types", failed=0)
        substation_id = _text(row, "substation_id")
        if substation_id:
            issues += self._asset_reference(
                substation_id,
                source_row,
                "substation_id",
                identifier,
                expected_type="substations",
            )
        issues += self._synthetic(row, source_row, identifier)
        return issues

    def _validate_telemetry(self, row: dict[str, str], source_row: int) -> list[Issue]:
        identifier = _text(row, "asset_id")
        issues = self._required(row, TELEMETRY_REQUIRED, source_row, identifier)
        issues += self._asset_reference(
            identifier, source_row, "asset_id", identifier
        )
        expected_type = self.asset_types.get(identifier)
        actual_type = _text(row, "asset_type")
        if expected_type is not None and actual_type and actual_type != expected_type:
            self.tracker.record("valid_asset_types", failed=1, detail=actual_type)
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "valid_asset_types",
                    "ERROR",
                    "asset_type",
                    f"asset_type '{actual_type}' does not match asset '{identifier}' ({expected_type})",
                )
            )
        else:
            self.tracker.record("valid_asset_types", failed=0)
        issues += self._timestamps(row, ["timestamp"], source_row, identifier)
        issues += self._numbers(
            row,
            TELEMETRY_RANGES,
            source_row,
            identifier,
        )
        issues += self._synthetic(row, source_row, identifier)

        missing = [name for name in TELEMETRY_OPTIONAL_SENSORS if not _text(row, name)]
        self.tracker.record(
            "telemetry_completeness",
            checked=len(TELEMETRY_OPTIONAL_SENSORS),
            failed=len(missing),
            detail=f"missing sensor fields: {', '.join(missing)}" if missing else None,
        )
        return issues

    def _validate_work_order(self, row: dict[str, str], source_row: int) -> list[Issue]:
        identifier = _text(row, "work_order_id")
        required = ["work_order_id", "synthetic"] + WORK_ORDER_REQUIRED_FIELDS
        issues = self._required(row, required, source_row, identifier)
        issues += self._identifier(identifier, source_row, "work_order_id")
        issues += self._asset_reference(
            _text(row, "asset_ref"), source_row, "asset_ref", identifier
        )
        for field_name, allowed in (
            ("work_type", WORK_TYPES),
            ("priority", PRIORITIES),
            ("status", WORK_STATUSES),
        ):
            issues += self._category(
                _text(row, field_name), allowed, field_name, source_row, identifier
            )
        issues += self._timestamps(
            row, ["opened_at", "completed_at"], source_row, identifier
        )

        status = _text(row, "status")
        opened_raw = _text(row, "opened_at")
        completed_raw = _text(row, "completed_at")
        opened = parse_ts(opened_raw)
        completed = parse_ts(completed_raw) if completed_raw else None
        transition_errors = []
        if status == "completed" and not completed_raw:
            transition_errors.append("status 'completed' requires completed_at")
        if status in {"open", "in_progress", "cancelled"} and completed_raw:
            transition_errors.append(f"status '{status}' must not have completed_at")
        self.tracker.record(
            "work_order_status_transitions",
            failed=1 if transition_errors else 0,
            detail=transition_errors[0] if transition_errors else None,
        )
        for message in transition_errors:
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "work_order_status_transitions",
                    "ERROR",
                    "status",
                    message,
                )
            )

        order_errors = []
        if opened is not None and completed is not None and completed < opened:
            order_errors.append("completed_at precedes opened_at")
        self.tracker.record(
            "completed_at_order",
            failed=1 if order_errors else 0,
            detail=order_errors[0] if order_errors else None,
        )
        for message in order_errors:
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "completed_at_order",
                    "ERROR",
                    "completed_at",
                    message,
                )
            )
        issues += self._synthetic(row, source_row, identifier)
        return issues

    def _validate_inspection(self, row: dict[str, str], source_row: int) -> list[Issue]:
        identifier = _text(row, "inspection_id")
        required = ["synthetic"] + INSPECTION_REQUIRED_FIELDS
        issues = self._required(row, required, source_row, identifier)
        issues += self._identifier(identifier, source_row, "inspection_id")
        issues += self._asset_reference(
            _text(row, "asset_ref"), source_row, "asset_ref", identifier
        )
        issues += self._category(
            _text(row, "condition"),
            INSPECTION_CONDITIONS,
            "condition",
            source_row,
            identifier,
        )
        issues += self._category(
            _text(row, "severity"),
            INSPECTION_SEVERITIES,
            "severity",
            source_row,
            identifier,
        )
        issues += self._timestamps(row, ["inspection_date"], source_row, identifier)
        issues += self._synthetic(row, source_row, identifier)
        return issues

    def _validate_failure(self, row: dict[str, str], source_row: int) -> list[Issue]:
        identifier = _text(row, "failure_id")
        required = ["failure_id", "synthetic"] + FAILURE_REQUIRED_FIELDS
        issues = self._required(row, required, source_row, identifier)
        issues += self._identifier(identifier, source_row, "failure_id")
        asset_ref = _text(row, "asset_ref")
        issues += self._asset_reference(asset_ref, source_row, "asset_ref", identifier)
        issues += self._category(
            _text(row, "failure_category"),
            FAILURE_CATEGORIES,
            "failure_category",
            source_row,
            identifier,
        )
        issues += self._timestamps(row, ["failure_timestamp"], source_row, identifier)
        issues += self._numbers(
            row,
            {"downtime_hours": FAILURE_RANGES["downtime_hours"]},
            source_row,
            identifier,
        )

        severity_raw = _text(row, "failure_severity")
        severity_issue = None
        try:
            severity = int(severity_raw)
            if not 1 <= severity <= 5:
                severity_issue = f"failure_severity {severity_raw} outside [1, 5]"
        except ValueError:
            severity_issue = f"non-integer failure_severity '{severity_raw}'"
        self.tracker.record(
            "failure_severity",
            failed=1 if severity_issue else 0,
            detail=severity_issue,
        )
        if severity_issue:
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "failure_severity",
                    "ERROR",
                    "failure_severity",
                    severity_issue,
                )
            )

        asset_type = self.asset_types.get(asset_ref)
        category = _text(row, "failure_category")
        if asset_type in CATEGORY_BY_ASSET_TYPE and category:
            if category not in CATEGORY_BY_ASSET_TYPE[asset_type]:
                message = (
                    f"failure category '{category}' is not valid for asset type '{asset_type}'"
                )
                self.tracker.record("category_values", failed=1, detail=message)
                issues.append(
                    self._issue(
                        source_row,
                        identifier,
                        "category_values",
                        "ERROR",
                        "failure_category",
                        message,
                    )
                )
        issues += self._synthetic(row, source_row, identifier)
        return issues

    def _validate_weather(self, row: dict[str, str], source_row: int) -> list[Issue]:
        identifier = _text(row, "weather_id")
        required = ["weather_id", "synthetic"] + WEATHER_REQUIRED_FIELDS
        issues = self._required(row, required, source_row, identifier)
        issues += self._identifier(identifier, source_row, "weather_id")
        issues += self._category(
            _text(row, "region"), REGIONS, "region", source_row, identifier
        )
        issues += self._timestamps(row, ["timestamp"], source_row, identifier)
        issues += self._numbers(row, WEATHER_RANGES, source_row, identifier)
        severe = _parse_bool(_text(row, "severe"))
        if severe is None:
            self.tracker.record("category_values", failed=1, detail="invalid severe boolean")
            issues.append(
                self._issue(
                    source_row,
                    identifier,
                    "category_values",
                    "ERROR",
                    "severe",
                    f"invalid boolean value '{_text(row, 'severe')}' in 'severe'",
                )
            )
        else:
            self.tracker.record("category_values", failed=0)
        issues += self._synthetic(row, source_row, identifier)
        return issues


def has_errors(issues: list[Issue]) -> bool:
    """Return True when any issue is a hard error."""
    return any(issue.severity == "ERROR" for issue in issues)
