"""Integration tests for the validated CSV-to-PostgreSQL ETL pipeline."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from backend.app.models import Asset, AssetTelemetry, IngestionRun, MaintenanceWorkOrder
from data_engineering.etl.config import DEFAULT_BATCH_SIZE, DEFAULT_INPUT_DIR, resolve_database_url
from data_engineering.etl import orchestrator as etl_orchestrator
from data_engineering.etl.orchestrator import run_ingestion

EXPECTED_SOURCE_ROWS = {
    "transformers": 1200,
    "substations": 300,
    "circuit_breakers": 800,
    "feeders": 300,
    "asset_telemetry": 75244,
    "work_orders": 1531,
    "inspections": 2586,
    "failures": 60,
    "weather": 1026,
}

EXPECTED_LOADED_ROWS = {
    "transformers": 1200,
    "substations": 300,
    "circuit_breakers": 800,
    "feeders": 300,
    "asset_telemetry": 75239,
    "work_orders": 1528,
    "inspections": 2584,
    "failures": 60,
    "weather": 1024,
}


def _test_url() -> str:
    """Return the dedicated integration-test database URL."""
    url = make_url(resolve_database_url()).set(database="gridops_test")
    return url.render_as_string(hide_password=False)


def _ingest(
    tmp_path: Path,
    *,
    dry_run: bool = False,
    fail_on_rejected: bool = False,
    input_dir: Path = DEFAULT_INPUT_DIR,
    batch_size: int = 1000,
) -> dict:
    return run_ingestion(
        input_dir=input_dir,
        batch_size=batch_size,
        dry_run=dry_run,
        fail_on_rejected=fail_on_rejected,
        report_dir=tmp_path / "reports",
        rejected_dir=tmp_path / "rejected",
        database_url=_test_url(),
    )


def _table_counts(db_session_factory, names) -> dict[str, int]:
    from backend.app.models import (
        CircuitBreakerDetail,
        FailureIncident,
        FeederDetail,
        Inspection,
        MaintenanceWorkOrder,
        SubstationDetail,
        TransformerDetail,
        WeatherObservation,
    )

    model_map = {
        "assets": Asset,
        "transformer_details": TransformerDetail,
        "substation_details": SubstationDetail,
        "circuit_breaker_details": CircuitBreakerDetail,
        "feeder_details": FeederDetail,
        "asset_telemetry": AssetTelemetry,
        "maintenance_work_orders": MaintenanceWorkOrder,
        "inspections": Inspection,
        "failure_incidents": FailureIncident,
        "weather_observations": WeatherObservation,
        "ingestion_runs": IngestionRun,
    }
    counts: dict[str, int] = {}
    from sqlalchemy import select

    with db_session_factory() as session:
        for name in names:
            counts[name] = int(
                session.scalar(select(func.count()).select_from(model_map[name].__table__)) or 0
            )
    return counts


def test_full_ingestion_loads_all_nine_datasets(ingested_db) -> None:
    """The first full ingestion completes with zero rejected source rows."""
    report = ingested_db
    assert report["status"] == "completed"
    assert report["totals"]["rows_rejected"] == 0
    datasets = {item["dataset"]: item for item in report["datasets"]}
    assert set(datasets) == set(EXPECTED_SOURCE_ROWS)
    for dataset, source_rows in EXPECTED_SOURCE_ROWS.items():
        assert datasets[dataset]["rows_read"] == source_rows
    assert report["totals"]["rows_read"] == sum(EXPECTED_SOURCE_ROWS.values())


def test_ingested_database_row_counts(db_session_factory, ingested_db) -> None:
    """Post-ingestion database counts match source-derived expectations."""
    counts = _table_counts(
        db_session_factory,
        [
            "assets",
            "asset_telemetry",
            "maintenance_work_orders",
            "inspections",
            "failure_incidents",
            "weather_observations",
            "ingestion_runs",
        ],
    )
    assert counts["asset_telemetry"] == EXPECTED_LOADED_ROWS["asset_telemetry"]
    assert counts["maintenance_work_orders"] == EXPECTED_LOADED_ROWS["work_orders"]
    assert counts["inspections"] == EXPECTED_LOADED_ROWS["inspections"]
    assert counts["failure_incidents"] == EXPECTED_LOADED_ROWS["failures"]
    assert counts["weather_observations"] == EXPECTED_LOADED_ROWS["weather"]


def test_repeated_ingestion_is_idempotent(db_session_factory, tmp_path: Path) -> None:
    """A repeated ingestion inserts nothing new and skips all previously loaded rows."""
    report = _ingest(tmp_path, batch_size=1000)
    assert report["status"] == "completed"
    assert report["totals"]["rows_inserted"] == 0
    assert report["totals"]["rows_updated"] == 0
    assert report["totals"]["rows_skipped"] == report["totals"]["rows_read"]
    assert report["totals"]["rows_rejected"] == 0


def test_dry_run_does_not_modify_database(db_session_factory, tmp_path: Path) -> None:
    """A dry run validates and reports without writing database rows."""
    names = [
        "assets",
        "asset_telemetry",
        "maintenance_work_orders",
        "inspections",
        "failure_incidents",
        "weather_observations",
    ]
    before = _table_counts(db_session_factory, names)
    report = _ingest(tmp_path, dry_run=True)
    after = _table_counts(db_session_factory, names)
    assert report["status"] == "dry_run"
    assert before == after


def test_invalid_rows_are_rejected_and_reported(tmp_path: Path, db_session_factory) -> None:
    """Invalid source rows are rejected with structured source context."""
    source_dir = tmp_path / "generated"
    source_dir.mkdir()
    for filename in [
        "transformers.csv",
        "substations.csv",
        "circuit_breakers.csv",
        "feeders.csv",
        "asset_telemetry.csv",
        "work_orders.csv",
        "inspections.csv",
        "failures.csv",
        "weather.csv",
    ]:
        shutil.copy(DEFAULT_INPUT_DIR / filename, source_dir / filename)

    work_orders_path = source_dir / "work_orders.csv"
    with work_orders_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    changed = False
    for row in rows:
        if row.get("status") == "completed":
            row["asset_ref"] = "NOPE-99999"
            changed = True
            break
    assert changed
    with work_orders_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    report = _ingest(tmp_path, input_dir=source_dir, fail_on_rejected=False)
    assert report["status"] == "completed_with_rejections"
    assert report["rejected_count"] == 1
    datasets = {item["dataset"]: item for item in report["datasets"]}
    assert datasets["work_orders"]["rows_rejected"] == 1
    rejected_payload = json.loads(
        (tmp_path / "rejected" / f"{report['run_id']}.json").read_text(encoding="utf-8")
    )
    assert rejected_payload["rejected_count"] == 1
    record = rejected_payload["records"][0]
    assert record["dataset"] == "work_orders"
    assert record["source_file"] == "work_orders.csv"
    assert record["source_row"] >= 2
    assert record["identifier"].startswith("WO-")
    assert record["field"] == "asset_ref"
    assert "broken asset reference" in record["reason"]


def test_failed_ingestion_reports_failed_status(db_session_factory, tmp_path: Path, monkeypatch) -> None:
    """Forced per-dataset load failures produce a failed ingestion run."""
    original = etl_orchestrator.upsert_rows

    def failing_upsert(session, model, rows, **kwargs):
        if model.__name__ == "AssetTelemetry":
            raise RuntimeError("forced telemetry load failure")
        return original(session, model, rows, **kwargs)

    monkeypatch.setattr(etl_orchestrator, "upsert_rows", failing_upsert)
    report = _ingest(tmp_path, batch_size=1000)
    assert report["status"] == "failed"
    assert report["error_summary"]
    with db_session_factory() as session:
        run = session.get(IngestionRun, report["run_id"])
        assert run is not None
        assert run.status == "failed"


def test_database_unique_and_foreign_key_constraints(db_session_factory) -> None:
    """Database primary keys and foreign keys reject duplicates and broken references."""
    from datetime import datetime

    with db_session_factory() as session:
        session.add(
            AssetTelemetry(
                telemetry_id="t-test-0001",
                asset_id="NOPE-99999",
                asset_type="transformers",
                timestamp=datetime(2026, 1, 1, 0, 0, 0),
                voltage_kv=100.0,
                operating_hours_cumulative=10,
                synthetic=True,
            )
        )
        session.add(
            Asset(
                asset_id="T-00001",
                asset_type="transformers",
                name="Duplicate",
                operating_hours_cumulative=10,
                status="active",
                synthetic=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
