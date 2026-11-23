"""Typed, database-independent input records for feature engineering.

The feature functions in this package never import SQLAlchemy.  They operate on
these small immutable records so they can be unit tested without a database and
reused from ETL, notebooks, or a batch job.  :mod:`ml.features.repository`
maps the ORM models in ``backend.app.models`` onto these records.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

# Event bound: either one global datetime or a per-asset mapping of
# ``asset_id -> failure timestamp``.
EventBound = datetime | Mapping[str, datetime] | None


@dataclass(frozen=True, slots=True)
class AssetRecord:
    """Static asset attributes from the unified ``assets`` dimension."""

    asset_id: str
    asset_type: str
    name: str | None = None
    install_date: date | None = None
    status: str | None = None
    region: str | None = None
    operating_hours_cumulative: int | None = None


@dataclass(frozen=True, slots=True)
class TelemetryReading:
    """One row from ``asset_telemetry``.

    Sensor columns are optional because the synthetic generator deliberately
    blanks roughly one percent of readings.  ``voltage_kv`` is non-nullable in
    the schema but is still typed as optional so the functions tolerate sparse
    or partially populated inputs.
    """

    asset_id: str
    timestamp: datetime
    temperature_c: float | None = None
    load_pct: float | None = None
    voltage_kv: float | None = None
    current_a: float | None = None
    vibration_mm_s: float | None = None
    operating_hours_cumulative: int | None = None


@dataclass(frozen=True, slots=True)
class WorkOrderRecord:
    """One row from ``maintenance_work_orders``."""

    work_order_id: str
    asset_id: str
    work_type: str
    priority: str
    status: str
    opened_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class InspectionRecord:
    """One row from ``inspections``."""

    inspection_id: str
    asset_id: str
    inspection_date: datetime
    condition: str
    severity: str
    findings: str | None = None


@dataclass(frozen=True, slots=True)
class WeatherRecord:
    """One row from ``weather_observations`` (regional, not asset-scoped)."""

    weather_id: str
    region: str
    timestamp: datetime
    temperature_c: float
    wind_speed_ms: float
    precipitation_mm: float
    severe: bool


@dataclass(frozen=True, slots=True)
class FailureRecord:
    """One row from ``failure_incidents``.

    This record is used only by :mod:`ml.features.labels`.  ``failure_severity``
    and ``downtime_hours`` are outcome attributes and must never be emitted as
    predictor features.
    """

    failure_id: str
    asset_id: str
    failure_category: str
    failure_timestamp: datetime
    failure_severity: int
    downtime_hours: float



def _as_bool(value: object) -> bool:
    """Coerce CSV-style booleans (``"true"``/``"false"``) safely."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _as_datetime(value: object) -> datetime | None:
    """Coerce a datetime or ISO-8601 string to a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    raise TypeError(f"expected datetime or ISO string, got {type(value).__name__}")


def _as_float(value: object) -> float | None:
    """Coerce a numeric database value to ``float``; blanks become ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return float(text)
    return float(value)  # type: ignore[arg-type]


def _as_int(value: object) -> int | None:
    """Coerce a numeric database value to ``int``; blanks become ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return int(float(text))
    return int(value)  # type: ignore[arg-type]


def telemetry_from_mapping(row: dict[str, object]) -> TelemetryReading:
    """Build a :class:`TelemetryReading` from a CSV-style mapping."""
    timestamp = _as_datetime(row.get("timestamp"))
    if timestamp is None:
        raise ValueError("telemetry row requires a 'timestamp'")
    return TelemetryReading(
        asset_id=str(row["asset_id"]),
        timestamp=timestamp,
        temperature_c=_as_float(row.get("temperature_c")),
        load_pct=_as_float(row.get("load_pct")),
        voltage_kv=_as_float(row.get("voltage_kv")),
        current_a=_as_float(row.get("current_a")),
        vibration_mm_s=_as_float(row.get("vibration_mm_s")),
        operating_hours_cumulative=_as_int(row.get("operating_hours_cumulative")),
    )


def work_order_from_mapping(row: dict[str, object]) -> WorkOrderRecord:
    """Build a :class:`WorkOrderRecord` from a CSV-style mapping."""
    opened_at = _as_datetime(row.get("opened_at"))
    if opened_at is None:
        raise ValueError("work order row requires an 'opened_at'")
    return WorkOrderRecord(
        work_order_id=str(row["work_order_id"]),
        asset_id=str(row["asset_id"]),
        work_type=str(row["work_type"]),
        priority=str(row["priority"]),
        status=str(row["status"]),
        opened_at=opened_at,
        completed_at=_as_datetime(row.get("completed_at")),
    )


def inspection_from_mapping(row: dict[str, object]) -> InspectionRecord:
    """Build an :class:`InspectionRecord` from a CSV-style mapping."""
    inspection_date = _as_datetime(row.get("inspection_date"))
    if inspection_date is None:
        raise ValueError("inspection row requires an 'inspection_date'")
    return InspectionRecord(
        inspection_id=str(row["inspection_id"]),
        asset_id=str(row["asset_id"]),
        inspection_date=inspection_date,
        condition=str(row["condition"]),
        severity=str(row["severity"]),
        findings=None if row.get("findings") is None else str(row["findings"]),
    )


def weather_from_mapping(row: dict[str, object]) -> WeatherRecord:
    """Build a :class:`WeatherRecord` from a CSV-style mapping."""
    timestamp = _as_datetime(row.get("timestamp"))
    if timestamp is None:
        raise ValueError("weather row requires a 'timestamp'")
    return WeatherRecord(
        weather_id=str(row["weather_id"]),
        region=str(row["region"]),
        timestamp=timestamp,
        temperature_c=float(row["temperature_c"]),  # type: ignore[arg-type]
        wind_speed_ms=float(row["wind_speed_ms"]),  # type: ignore[arg-type]
        precipitation_mm=float(row["precipitation_mm"]),  # type: ignore[arg-type]
        severe=_as_bool(row["severe"]),
    )


def failure_from_mapping(row: dict[str, object]) -> FailureRecord:
    """Build a :class:`FailureRecord` from a CSV-style mapping."""
    timestamp = _as_datetime(row.get("failure_timestamp"))
    if timestamp is None:
        raise ValueError("failure row requires a 'failure_timestamp'")
    return FailureRecord(
        failure_id=str(row["failure_id"]),
        asset_id=str(row["asset_id"]),
        failure_category=str(row["failure_category"]),
        failure_timestamp=timestamp,
        failure_severity=int(row["failure_severity"]),  # type: ignore[arg-type]
        downtime_hours=float(row["downtime_hours"]),  # type: ignore[arg-type]
    )

