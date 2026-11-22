"""Typed transformations from CSV strings to SQLAlchemy model dictionaries."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from data_engineering.generators.base import parse_ts
from data_engineering.etl.config import ASSET_DATASETS, DATASET_ID_FIELDS
from data_engineering.etl.validation import row_fingerprint


class TransformError(ValueError):
    """Raised when a value cannot be converted to its database type."""


def text(row: dict[str, str], field_name: str) -> str:
    """Return a stripped string value."""
    return str(row.get(field_name, "") or "").strip()


def to_decimal(value: str, *, field_name: str) -> Decimal:
    """Convert a required decimal field."""
    raw = value.strip()
    if not raw:
        raise TransformError(f"required numeric field '{field_name}' is empty")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise TransformError(f"invalid decimal '{raw}' in '{field_name}'") from exc


def to_optional_decimal(value: str, *, field_name: str) -> Decimal | None:
    """Convert an optional decimal field; blanks become ``None``."""
    if not value.strip():
        return None
    return to_decimal(value, field_name=field_name)


def to_int(value: str, *, field_name: str) -> int:
    """Convert a required integer field."""
    raw = value.strip()
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise TransformError(f"invalid integer '{raw}' in '{field_name}'") from exc


def to_bool(value: str, *, field_name: str) -> bool:
    """Convert ``true``/``false`` source markers to a boolean."""
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise TransformError(f"invalid boolean '{value}' in '{field_name}'")


def to_datetime(value: str, *, field_name: str) -> datetime:
    """Convert an ISO-8601 source timestamp."""
    parsed = parse_ts(value)
    if parsed is None:
        raise TransformError(f"invalid timestamp '{value}' in '{field_name}'")
    return parsed


def to_optional_datetime(value: str, *, field_name: str) -> datetime | None:
    """Convert an optional ISO-8601 source timestamp."""
    if not value.strip():
        return None
    return to_datetime(value, field_name=field_name)


def to_date(value: str, *, field_name: str) -> date:
    """Convert an ISO-8601 date or timestamp to a date."""
    return to_datetime(value, field_name=field_name).date()


def to_optional_date(value: str, *, field_name: str) -> date | None:
    """Convert an optional date field."""
    if not value.strip():
        return None
    return to_date(value, field_name=field_name)


def dataset_key(dataset: str, row: dict[str, str]) -> str:
    """Return the idempotency key for a source row.

    Telemetry has no natural identifier; its key is the SHA-256 digest of the
    full normalized row.  All other datasets use their declared source ID.
    """
    if dataset == "asset_telemetry":
        return row_fingerprint(row)
    field_name = DATASET_ID_FIELDS[dataset]
    return text(row, field_name)


def dataset_fingerprint(dataset: str, row: dict[str, str]) -> str:
    """Return a content fingerprint used to distinguish exact duplicates."""
    return row_fingerprint(row)


def identifier_for(dataset: str, row: dict[str, str]) -> str | None:
    """Best-effort identifier for a rejected-row report."""
    if dataset == "asset_telemetry":
        asset_id = text(row, "asset_id")
        return asset_id or None
    field_name = DATASET_ID_FIELDS.get(dataset)
    return text(row, field_name) if field_name else None


def asset_values(dataset: str, row: dict[str, str]) -> dict[str, Any]:
    """Map an asset CSV row to the unified ``assets`` table."""
    id_field = DATASET_ID_FIELDS[dataset]
    return {
        "asset_id": text(row, id_field),
        "asset_type": text(row, "asset_type"),
        "name": text(row, "name"),
        "install_date": to_optional_date(text(row, "install_date"), field_name="install_date"),
        "operating_hours_cumulative": to_int(
            text(row, "operating_hours_cumulative"), field_name="operating_hours_cumulative"
        ),
        "status": text(row, "status"),
        "region": text(row, "region") or None,
        "synthetic": to_bool(text(row, "synthetic"), field_name="synthetic"),
    }


def detail_values(dataset: str, row: dict[str, str]) -> dict[str, Any]:
    """Map an asset CSV row to its type-specific detail table."""
    asset_id = text(row, DATASET_ID_FIELDS[dataset])
    if dataset == "substations":
        return {
            "asset_id": asset_id,
            "nominal_kv": to_decimal(text(row, "nominal_kv"), field_name="nominal_kv"),
            "area_sq_mi": to_decimal(text(row, "area_sq_mi"), field_name="area_sq_mi"),
            "equipment_count": to_int(text(row, "equipment_count"), field_name="equipment_count"),
        }
    if dataset == "transformers":
        return {
            "asset_id": asset_id,
            "substation_id": text(row, "substation_id"),
            "winding_type": text(row, "winding_type"),
            "rating_mva": to_decimal(text(row, "rating_mva"), field_name="rating_mva"),
            "primary_kv": to_decimal(text(row, "primary_kv"), field_name="primary_kv"),
            "secondary_kv": to_decimal(text(row, "secondary_kv"), field_name="secondary_kv"),
        }
    if dataset == "circuit_breakers":
        return {
            "asset_id": asset_id,
            "substation_id": text(row, "substation_id"),
            "panel_id": text(row, "panel_id"),
            "rated_current_a": to_decimal(
                text(row, "rated_current_a"), field_name="rated_current_a"
            ),
            "voltage_class": text(row, "voltage_class"),
        }
    if dataset == "feeders":
        return {
            "asset_id": asset_id,
            "substation_id": text(row, "substation_id"),
            "voltage_kv": to_decimal(text(row, "voltage_kv"), field_name="voltage_kv"),
            "capacity_kva": to_decimal(text(row, "capacity_kva"), field_name="capacity_kva"),
            "length_km": to_decimal(text(row, "length_km"), field_name="length_km"),
            "outage_count": to_int(text(row, "outage_count"), field_name="outage_count"),
        }
    raise TransformError(f"Unknown asset dataset: {dataset}")


def telemetry_values(row: dict[str, str]) -> dict[str, Any]:
    """Map a telemetry row, preserving intentional null sensor readings."""
    return {
        "telemetry_id": row_fingerprint(row),
        "asset_id": text(row, "asset_id"),
        "asset_type": text(row, "asset_type"),
        "timestamp": to_datetime(text(row, "timestamp"), field_name="timestamp"),
        "temperature_c": to_optional_decimal(
            text(row, "temperature_c"), field_name="temperature_c"
        ),
        "load_pct": to_optional_decimal(text(row, "load_pct"), field_name="load_pct"),
        "voltage_kv": to_decimal(text(row, "voltage_kv"), field_name="voltage_kv"),
        "current_a": to_optional_decimal(text(row, "current_a"), field_name="current_a"),
        "vibration_mm_s": to_optional_decimal(
            text(row, "vibration_mm_s"), field_name="vibration_mm_s"
        ),
        "operating_hours_cumulative": to_int(
            text(row, "operating_hours_cumulative"), field_name="operating_hours_cumulative"
        ),
        "synthetic": to_bool(text(row, "synthetic"), field_name="synthetic"),
    }


def work_order_values(row: dict[str, str]) -> dict[str, Any]:
    """Map a maintenance work-order row."""
    return {
        "work_order_id": text(row, "work_order_id"),
        "asset_id": text(row, "asset_ref"),
        "work_type": text(row, "work_type"),
        "priority": text(row, "priority"),
        "status": text(row, "status"),
        "opened_at": to_datetime(text(row, "opened_at"), field_name="opened_at"),
        "completed_at": to_optional_datetime(
            text(row, "completed_at"), field_name="completed_at"
        ),
        "synthetic": to_bool(text(row, "synthetic"), field_name="synthetic"),
    }


def inspection_values(row: dict[str, str]) -> dict[str, Any]:
    """Map an inspection row."""
    return {
        "inspection_id": text(row, "inspection_id"),
        "asset_id": text(row, "asset_ref"),
        "inspection_date": to_datetime(
            text(row, "inspection_date"), field_name="inspection_date"
        ),
        "condition": text(row, "condition"),
        "findings": text(row, "findings"),
        "severity": text(row, "severity"),
        "synthetic": to_bool(text(row, "synthetic"), field_name="synthetic"),
    }


def failure_values(row: dict[str, str]) -> dict[str, Any]:
    """Map a failure incident row."""
    return {
        "failure_id": text(row, "failure_id"),
        "asset_id": text(row, "asset_ref"),
        "failure_category": text(row, "failure_category"),
        "failure_timestamp": to_datetime(
            text(row, "failure_timestamp"), field_name="failure_timestamp"
        ),
        "failure_severity": to_int(
            text(row, "failure_severity"), field_name="failure_severity"
        ),
        "downtime_hours": to_decimal(
            text(row, "downtime_hours"), field_name="downtime_hours"
        ),
        "synthetic": to_bool(text(row, "synthetic"), field_name="synthetic"),
    }


def weather_values(row: dict[str, str]) -> dict[str, Any]:
    """Map a weather observation row."""
    return {
        "weather_id": text(row, "weather_id"),
        "region": text(row, "region"),
        "timestamp": to_datetime(text(row, "timestamp"), field_name="timestamp"),
        "temperature_c": to_decimal(
            text(row, "temperature_c"), field_name="temperature_c"
        ),
        "wind_speed_ms": to_decimal(
            text(row, "wind_speed_ms"), field_name="wind_speed_ms"
        ),
        "precipitation_mm": to_decimal(
            text(row, "precipitation_mm"), field_name="precipitation_mm"
        ),
        "severe": to_bool(text(row, "severe"), field_name="severe"),
        "synthetic": to_bool(text(row, "synthetic"), field_name="synthetic"),
    }


TRANSFORMERS = {
    "asset_telemetry": telemetry_values,
    "work_orders": work_order_values,
    "inspections": inspection_values,
    "failures": failure_values,
    "weather": weather_values,
}

__all__ = [
    "ASSET_DATASETS",
    "TransformError",
    "asset_values",
    "dataset_fingerprint",
    "dataset_key",
    "detail_values",
    "identifier_for",
    "TRANSFORMERS",
]
