"""Transactional PostgreSQL upserts with insert/update/skip accounting."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import Table, func, literal_column, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.app.models import (
    Asset,
    AssetTelemetry,
    CircuitBreakerDetail,
    DataQualityResult,
    FailureIncident,
    FeederDetail,
    IngestionDatasetResult,
    IngestionRun,
    Inspection,
    MaintenanceWorkOrder,
    SubstationDetail,
    TransformerDetail,
    WeatherObservation,
)

MODEL_BY_DATASET = {
    "transformers": Asset,
    "substations": Asset,
    "circuit_breakers": Asset,
    "feeders": Asset,
    "asset_telemetry": AssetTelemetry,
    "work_orders": MaintenanceWorkOrder,
    "inspections": Inspection,
    "failures": FailureIncident,
    "weather": WeatherObservation,
}

DETAIL_MODEL_BY_DATASET = {
    "transformers": TransformerDetail,
    "substations": SubstationDetail,
    "circuit_breakers": CircuitBreakerDetail,
    "feeders": FeederDetail,
}

KEY_COLUMNS = {
    "assets": ("asset_id",),
    "transformer_details": ("asset_id",),
    "substation_details": ("asset_id",),
    "circuit_breaker_details": ("asset_id",),
    "feeder_details": ("asset_id",),
    "asset_telemetry": ("telemetry_id",),
    "maintenance_work_orders": ("work_order_id",),
    "inspections": ("inspection_id",),
    "failure_incidents": ("failure_id",),
    "weather_observations": ("weather_id",),
}

# Telemetry rows are immutable by content hash, so conflicts are skipped rather
# than updated.  Every other table is upserted from the current source row.
UPDATE_COLUMNS = {
    "assets": (
        "asset_type",
        "name",
        "install_date",
        "operating_hours_cumulative",
        "status",
        "region",
        "synthetic",
    ),
    "transformer_details": (
        "substation_id",
        "winding_type",
        "rating_mva",
        "primary_kv",
        "secondary_kv",
    ),
    "substation_details": ("nominal_kv", "area_sq_mi", "equipment_count"),
    "circuit_breaker_details": (
        "substation_id",
        "panel_id",
        "rated_current_a",
        "voltage_class",
    ),
    "feeder_details": (
        "substation_id",
        "voltage_kv",
        "capacity_kva",
        "length_km",
        "outage_count",
    ),
    "asset_telemetry": (),
    "maintenance_work_orders": (
        "asset_id",
        "work_type",
        "priority",
        "status",
        "opened_at",
        "completed_at",
        "synthetic",
    ),
    "inspections": (
        "asset_id",
        "inspection_date",
        "condition",
        "findings",
        "severity",
        "synthetic",
    ),
    "failure_incidents": (
        "asset_id",
        "failure_category",
        "failure_timestamp",
        "failure_severity",
        "downtime_hours",
        "synthetic",
    ),
    "weather_observations": (
        "region",
        "timestamp",
        "temperature_c",
        "wind_speed_ms",
        "precipitation_mm",
        "severe",
        "synthetic",
    ),
}


def _table(model: type) -> Table:
    return model.__table__  # type: ignore[attr-defined]


def upsert_rows(
    session: Session,
    model: type,
    rows: Sequence[dict[str, Any]],
    *,
    chunk_size: int = 1_000,
    return_statuses: bool = False,
) -> dict[str, Any]:
    """Upsert rows and return ``inserted``, ``updated``, and optional statuses.

    The PostgreSQL ``xmax = 0`` returning expression distinguishes newly
    inserted rows from updated rows.  A conflict whose business columns are all
    identical is left untouched and is reported as skipped by the caller.
    """
    if not rows:
        return {"inserted": 0, "updated": 0, "statuses": {}}

    table = _table(model)
    key_columns = KEY_COLUMNS[table.name]
    update_columns = UPDATE_COLUMNS[table.name]
    inserted = 0
    updated = 0
    statuses: dict[str, str] = {}

    for start in range(0, len(rows), chunk_size):
        batch = list(rows[start : start + chunk_size])
        statement = pg_insert(table).values(batch)
        key_columns_sql = [table.c[name] for name in key_columns]

        if update_columns:
            excluded = statement.excluded
            set_values = {name: getattr(excluded, name) for name in update_columns}
            if "updated_at" in table.c:
                set_values["updated_at"] = func.now()
            comparisons = [
                table.c[name].is_distinct_from(getattr(excluded, name))
                for name in update_columns
            ]
            statement = statement.on_conflict_do_update(
                index_elements=key_columns_sql,
                set_=set_values,
                where=or_(*comparisons) if comparisons else None,
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=key_columns_sql)

        statement = statement.returning(
            *key_columns_sql,
            literal_column("xmax = 0").label("was_inserted"),
        )
        for result_row in session.execute(statement):
            key_value = result_row[0]
            was_inserted = bool(result_row[-1])
            inserted += 1 if was_inserted else 0
            updated += 0 if was_inserted else 1
            if return_statuses:
                statuses[str(key_value)] = "inserted" if was_inserted else "updated"

    return {"inserted": inserted, "updated": updated, "statuses": statuses}


def persist_dataset_result(session: Session, run_id, result: dict[str, Any]) -> None:
    """Persist one per-dataset ingestion result."""
    session.add(
        IngestionDatasetResult(
            run_id=run_id,
            dataset_name=result["dataset"],
            source_file=result["source_file"],
            status=result["status"],
            rows_read=result["rows_read"],
            rows_inserted=result["rows_inserted"],
            rows_updated=result["rows_updated"],
            rows_skipped=result["rows_skipped"],
            rows_rejected=result["rows_rejected"],
            validation_errors=result["validation_errors"],
            validation_warnings=result["validation_warnings"],
            duration_ms=result["duration_ms"],
            error_summary=result.get("error_summary"),
        )
    )


def persist_quality_results(
    session: Session, run_id, dataset: str, checks: Iterable[dict[str, Any]]
) -> None:
    """Persist quality-check counts for one dataset."""
    for check in checks:
        session.add(
            DataQualityResult(
                run_id=run_id,
                dataset_name=dataset,
                check_name=check["check_name"],
                severity=check["severity"],
                records_checked=check["records_checked"],
                records_passed=check["records_passed"],
                records_failed=check["records_failed"],
                details={
                    "failure_rate": check["failure_rate"],
                    "samples": check["samples"],
                },
            )
        )


def count_rows(session: Session, model: type) -> int:
    """Return the current row count for a model."""
    return int(session.scalar(func.count().select().select_from(_table(model))) or 0)


__all__ = [
    "DETAIL_MODEL_BY_DATASET",
    "MODEL_BY_DATASET",
    "count_rows",
    "persist_dataset_result",
    "persist_quality_results",
    "upsert_rows",
]
