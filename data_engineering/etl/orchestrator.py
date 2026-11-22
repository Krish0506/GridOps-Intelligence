"""CLI and orchestration for validated, idempotent CSV ingestion.

Execution model:

* Asset rows are validated and upserted into the unified ``assets`` table.
* Detail tables are loaded after all assets so substation foreign keys resolve.
* Telemetry and event datasets stream in configurable batches.
* Each dataset uses its own transaction.  A failed dataset is rolled back and
  recorded as failed; other datasets may still complete.
* Every run writes a JSON report and a rejected-row report.  Database writes
  include per-dataset counts and persisted data-quality results.
"""

from __future__ import annotations

import argparse
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models import (
    Asset,
    AssetTelemetry,
    DataQualityResult,
    FailureIncident,
    IngestionDatasetResult,
    IngestionRun,
    Inspection,
    MaintenanceWorkOrder,
    WeatherObservation,
)
from data_engineering.etl.config import (
    ASSET_DATASETS,
    DATASET_FILES,
    DATASET_ID_FIELDS,
    DEFAULT_INPUT_DIR,
    DEFAULT_REJECTED_DIR,
    DEFAULT_REPORT_DIR,
    DEPENDENT_DATASETS,
    DETAIL_LOAD_ORDER,
    EtlSettings,
    PROJECT_ROOT,
    resolve_database_url,
    sanitized_destination,
)
from data_engineering.etl.csv_reader import CsvFormatError, iter_rows
from data_engineering.etl.loader import (
    DETAIL_MODEL_BY_DATASET,
    MODEL_BY_DATASET,
    persist_dataset_result,
    persist_quality_results,
    upsert_rows,
)
from data_engineering.etl.reporting import write_ingestion_report, write_rejected_rows
from data_engineering.etl.transformers import (
    TRANSFORMERS,
    TransformError,
    asset_values,
    dataset_fingerprint,
    dataset_key,
    detail_values,
    identifier_for,
)
from data_engineering.etl.validation import (
    DuplicateTracker,
    Issue,
    QualityTracker,
    RowValidator,
    has_errors,
)

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_dicts(issues: Sequence[Issue]) -> list[dict[str, Any]]:
    return [issue.to_dict() for issue in issues]


def _rejected_record(
    dataset: str, source_file: str, issue: Issue
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "source_file": source_file,
        "source_row": issue.source_row,
        "identifier": issue.identifier,
        "field": issue.field,
        "reason": issue.message,
        "check": issue.check,
        "severity": issue.severity,
    }


def _new_dataset_result(dataset: str, source_file: str) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "source_file": source_file,
        "status": "completed",
        "rows_read": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_skipped": 0,
        "rows_rejected": 0,
        "rows_valid": 0,
        "validation_errors": 0,
        "validation_warnings": 0,
        "duration_ms": 0,
        "error_summary": None,
        "completeness": 1.0,
        "duplicate_rate": 0.0,
        "quality_checks": [],
    }


def load_asset_registry(input_dir: Path) -> tuple[dict[str, str], set[str]]:
    """Read all asset CSVs to build the ID/type registry used for FK checks."""
    asset_types: dict[str, str] = {}
    substation_ids: set[str] = set()
    for dataset in ASSET_DATASETS:
        id_field = DATASET_ID_FIELDS[dataset]
        for _, row in iter_rows(input_dir / DATASET_FILES[dataset], dataset):
            asset_id = str(row.get(id_field, "") or "").strip()
            if not asset_id:
                continue
            asset_types[asset_id] = dataset
            if dataset == "substations":
                substation_ids.add(asset_id)
    return asset_types, substation_ids


def _finalize_quality(
    result: dict[str, Any], tracker: QualityTracker
) -> None:
    checks = tracker.results()
    result["quality_checks"] = checks
    required = next(
        (check for check in checks if check["check_name"] == "required_field_completeness"),
        None,
    )
    if required and required["records_checked"]:
        result["completeness"] = round(
            required["records_passed"] / required["records_checked"], 6
        )
    duplicate = next(
        (check for check in checks if check["check_name"] == "duplicate_detection"),
        None,
    )
    if duplicate and duplicate["records_checked"]:
        result["duplicate_rate"] = duplicate["failure_rate"]


def _read_asset_dataset(
    dataset: str,
    input_dir: Path,
    registry: dict[str, str],
    substation_ids: set[str],
    rejected: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate one asset CSV and retain rows for the two-phase load."""
    source_file = DATASET_FILES[dataset]
    result = _new_dataset_result(dataset, source_file)
    tracker = QualityTracker(dataset)
    validator = RowValidator(dataset, registry, substation_ids, tracker)
    duplicates = DuplicateTracker()
    started = time.perf_counter()
    asset_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    exact_duplicates = 0

    for source_row, row in iter_rows(input_dir / source_file, dataset):
        result["rows_read"] += 1
        issues = validator.validate(row, source_row)
        errors = [issue for issue in issues if issue.severity == "ERROR"]
        result["validation_errors"] += len(errors)
        result["validation_warnings"] += sum(
            1 for issue in issues if issue.severity == "WARNING"
        )
        if errors:
            result["rows_rejected"] += 1
            rejected.extend(_rejected_record(dataset, source_file, issue) for issue in errors)
            continue

        key = dataset_key(dataset, row)
        fingerprint = dataset_fingerprint(dataset, row)
        duplicate_status = duplicates.classify(key, fingerprint)
        if duplicate_status == "exact":
            exact_duplicates += 1
            result["validation_warnings"] += 1
            tracker.record(
                "duplicate_detection",
                failed=1,
                detail=f"exact duplicate identifier {key}",
            )
            continue
        if duplicate_status == "conflict":
            result["rows_rejected"] += 1
            result["validation_errors"] += 1
            tracker.record(
                "duplicate_detection",
                failed=1,
                detail=f"conflicting duplicate identifier {key}",
            )
            issue = Issue(
                dataset,
                source_row,
                key,
                "duplicate_detection",
                "ERROR",
                "asset_id",
                f"conflicting duplicate identifier '{key}'",
            )
            rejected.append(_rejected_record(dataset, source_file, issue))
            continue
        tracker.record("duplicate_detection", failed=0)

        try:
            asset_row = asset_values(dataset, row)
            detail_row = detail_values(dataset, row)
        except TransformError as exc:
            result["rows_rejected"] += 1
            result["validation_errors"] += 1
            issue = Issue(
                dataset,
                source_row,
                identifier_for(dataset, row),
                "numeric_ranges",
                "ERROR",
                None,
                str(exc),
            )
            rejected.append(_rejected_record(dataset, source_file, issue))
            continue
        asset_rows.append(asset_row)
        detail_rows.append(detail_row)
        result["rows_valid"] += 1

    result["exact_duplicates"] = exact_duplicates
    result["asset_rows"] = asset_rows
    result["detail_rows"] = detail_rows
    result["status"] = (
        "completed_with_rejections" if result["rows_rejected"] else "completed"
    )
    result["duration_ms"] = int((time.perf_counter() - started) * 1000)
    _finalize_quality(result, tracker)
    return result


def _load_assets(
    session_factory: sessionmaker[Session],
    states: list[dict[str, Any]],
    batch_size: int,
) -> dict[str, dict[str, str]]:
    """Upsert all asset rows and return per-dataset id -> status maps."""
    all_rows = [row for state in states for row in state["asset_rows"]]
    statuses: dict[str, dict[str, str]] = {}
    with session_factory() as session, session.begin():
        response = upsert_rows(
            session, Asset, all_rows, chunk_size=batch_size, return_statuses=True
        )
    for state in states:
        dataset = state["dataset"]
        statuses[dataset] = {
            row["asset_id"]: response["statuses"].get(row["asset_id"], "skipped")
            for row in state["asset_rows"]
        }
    return statuses


def _load_details(
    session_factory: sessionmaker[Session],
    state: dict[str, Any],
    batch_size: int,
) -> dict[str, str]:
    """Upsert one asset type's detail rows."""
    model = DETAIL_MODEL_BY_DATASET[state["dataset"]]
    with session_factory() as session, session.begin():
        response = upsert_rows(
            session,
            model,
            state["detail_rows"],
            chunk_size=batch_size,
            return_statuses=True,
        )
    return response["statuses"]


def _apply_asset_counts(
    state: dict[str, Any],
    asset_statuses: dict[str, str],
    detail_statuses: dict[str, str],
) -> None:
    inserted = updated = 0
    for row in state["asset_rows"]:
        asset_id = row["asset_id"]
        asset_status = asset_statuses.get(asset_id, "skipped")
        detail_status = detail_statuses.get(asset_id, "skipped")
        if asset_status == "inserted" or detail_status == "inserted":
            inserted += 1
        elif asset_status == "updated" or detail_status == "updated":
            updated += 1
    state["rows_inserted"] = inserted
    state["rows_updated"] = updated
    state["rows_skipped"] = (
        state["exact_duplicates"]
        + max(0, state["rows_valid"] - inserted - updated)
    )


def _persist_observability(
    session_factory: sessionmaker[Session],
    run_id: uuid.UUID,
    result: dict[str, Any],
) -> None:
    with session_factory() as session, session.begin():
        persist_dataset_result(session, run_id, result)
        persist_quality_results(
            session, run_id, result["dataset"], result["quality_checks"]
        )


def _stream_dependent_dataset(
    dataset: str,
    input_dir: Path,
    registry: dict[str, str],
    substation_ids: set[str],
    rejected: list[dict[str, Any]],
    session_factory: sessionmaker[Session] | None,
    batch_size: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Validate and load a telemetry or event dataset in bounded batches."""
    source_file = DATASET_FILES[dataset]
    result = _new_dataset_result(dataset, source_file)
    tracker = QualityTracker(dataset)
    validator = RowValidator(dataset, registry, substation_ids, tracker)
    duplicates = DuplicateTracker()
    transform = TRANSFORMERS[dataset]
    model = MODEL_BY_DATASET[dataset]
    started = time.perf_counter()
    buffer: list[dict[str, Any]] = []
    inserted = updated = 0
    exact_duplicates = 0

    def flush(session: Session | None) -> None:
        nonlocal buffer, inserted, updated
        if not buffer:
            return
        if session is not None:
            response = upsert_rows(
                session, model, buffer, chunk_size=batch_size, return_statuses=False
            )
            inserted += response["inserted"]
            updated += response["updated"]
        buffer = []

    try:
        if dry_run:
            session_context = None
        else:
            assert session_factory is not None
            session_context = session_factory()
        session = session_context
        try:
            if session is not None:
                session.begin()
            for source_row, row in iter_rows(input_dir / source_file, dataset):
                result["rows_read"] += 1
                issues = validator.validate(row, source_row)
                errors = [issue for issue in issues if issue.severity == "ERROR"]
                result["validation_errors"] += len(errors)
                result["validation_warnings"] += sum(
                    1 for issue in issues if issue.severity == "WARNING"
                )
                if errors:
                    result["rows_rejected"] += 1
                    rejected.extend(
                        _rejected_record(dataset, source_file, issue) for issue in errors
                    )
                    continue

                key = dataset_key(dataset, row)
                fingerprint = dataset_fingerprint(dataset, row)
                duplicate_status = duplicates.classify(key, fingerprint)
                if duplicate_status == "exact":
                    exact_duplicates += 1
                    result["validation_warnings"] += 1
                    tracker.record(
                        "duplicate_detection",
                        failed=1,
                        detail=f"exact duplicate record at row {source_row}",
                    )
                    continue
                if duplicate_status == "conflict":
                    result["rows_rejected"] += 1
                    result["validation_errors"] += 1
                    tracker.record(
                        "duplicate_detection",
                        failed=1,
                        detail=f"conflicting duplicate identifier {key}",
                    )
                    issue = Issue(
                        dataset,
                        source_row,
                        key,
                        "duplicate_detection",
                        "ERROR",
                        "identifier",
                        f"conflicting duplicate identifier '{key}'",
                    )
                    rejected.append(_rejected_record(dataset, source_file, issue))
                    continue
                tracker.record("duplicate_detection", failed=0)

                try:
                    buffer.append(transform(row))
                except TransformError as exc:
                    result["rows_rejected"] += 1
                    result["validation_errors"] += 1
                    issue = Issue(
                        dataset,
                        source_row,
                        identifier_for(dataset, row),
                        "numeric_ranges",
                        "ERROR",
                        None,
                        str(exc),
                    )
                    rejected.append(_rejected_record(dataset, source_file, issue))
                    continue
                result["rows_valid"] += 1
                if len(buffer) >= batch_size:
                    flush(session)

            flush(session)
            if session is not None:
                session.commit()
        except Exception:
            if session is not None:
                session.rollback()
            raise
        finally:
            if session is not None:
                session.close()
    except Exception as exc:
        result["status"] = "failed"
        result["error_summary"] = f"{type(exc).__name__}: {exc}"
        result["rows_inserted"] = 0
        result["rows_updated"] = 0
        result["rows_skipped"] = exact_duplicates
        result["duration_ms"] = int((time.perf_counter() - started) * 1000)
        _finalize_quality(result, tracker)
        return result

    result["exact_duplicates"] = exact_duplicates
    result["rows_inserted"] = inserted
    result["rows_updated"] = updated
    result["rows_skipped"] = (
        exact_duplicates
        if dry_run
        else exact_duplicates + max(0, result["rows_valid"] - inserted - updated)
    )
    result["status"] = (
        "completed_with_rejections" if result["rows_rejected"] else "completed"
    )
    result["duration_ms"] = int((time.perf_counter() - started) * 1000)
    _finalize_quality(result, tracker)
    return result


def _database_counts(session_factory: sessionmaker[Session]) -> dict[str, int]:
    from backend.app.models import (
        CircuitBreakerDetail,
        FeederDetail,
        SubstationDetail,
        TransformerDetail,
    )

    models = {
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
    }
    counts: dict[str, int] = {}
    with session_factory() as session:
        for name, model in models.items():
            counts[name] = int(
                session.scalar(func.count().select().select_from(model.__table__)) or 0
            )
    return counts


def run_ingestion(
    *,
    input_dir: Path | str | None = None,
    batch_size: int | None = None,
    dry_run: bool = False,
    fail_on_rejected: bool = False,
    report_dir: Path | str | None = None,
    rejected_dir: Path | str | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Run the full ingestion workflow and return the structured report."""
    settings = EtlSettings()
    input_path = Path(input_dir) if input_dir is not None else settings.input_dir
    report_path_dir = Path(report_dir) if report_dir is not None else settings.report_dir
    rejected_path_dir = (
        Path(rejected_dir) if rejected_dir is not None else settings.rejected_dir
    )
    effective_batch_size = batch_size or settings.batch_size
    if effective_batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    run_id = uuid.uuid4()
    started_at = _utc_now()
    resolved_url = resolve_database_url(database_url)
    destination = sanitized_destination(resolved_url)
    engine = None if dry_run else create_engine(resolved_url, pool_pre_ping=True)
    session_factory = (
        None if engine is None else sessionmaker(bind=engine, expire_on_commit=False)
    )
    rejected: list[dict[str, Any]] = []
    dataset_results: list[dict[str, Any]] = []
    run_row_created = False
    fatal_error: str | None = None

    if not dry_run:
        assert session_factory is not None
        try:
            with session_factory() as session, session.begin():
                session.add(
                    IngestionRun(
                        run_id=run_id,
                        source_name="synthetic_csv_bundle",
                        started_at=started_at,
                        status="running",
                        dry_run=False,
                    )
                )
            run_row_created = True
        except Exception as exc:
            fatal_error = f"Could not create ingestion run: {type(exc).__name__}: {exc}"

    if fatal_error is None:
        try:
            registry, substation_ids = load_asset_registry(input_path)
        except Exception as exc:
            fatal_error = f"{type(exc).__name__}: {exc}"

    if fatal_error is None:
        for dataset in ASSET_DATASETS:
            try:
                state = _read_asset_dataset(
                    dataset, input_path, registry, substation_ids, rejected
                )
            except Exception as exc:
                state = _new_dataset_result(dataset, DATASET_FILES[dataset])
                state["status"] = "failed"
                state["error_summary"] = f"{type(exc).__name__}: {exc}"
                state["asset_rows"] = []
                state["detail_rows"] = []
                state["exact_duplicates"] = 0
            dataset_results.append(state)

        assets_loaded = dry_run
        if not dry_run:
            assert session_factory is not None
            try:
                asset_statuses = _load_assets(
                    session_factory,
                    [state for state in dataset_results if state["status"] != "failed"],
                    effective_batch_size,
                )
                for state in dataset_results:
                    if state["status"] == "failed":
                        continue
                    state["asset_statuses"] = asset_statuses[state["dataset"]]
                assets_loaded = True
            except Exception as exc:
                for state in dataset_results:
                    if state["status"] != "failed":
                        state["status"] = "failed"
                        state["error_summary"] = (
                            f"asset load failed: {type(exc).__name__}: {exc}"
                        )

        detail_statuses: dict[str, dict[str, str]] = {}
        if not dry_run:
            assert session_factory is not None
            for dataset in DETAIL_LOAD_ORDER:
                state = next(item for item in dataset_results if item["dataset"] == dataset)
                if state["status"] == "failed":
                    continue
                try:
                    detail_statuses[dataset] = _load_details(
                        session_factory, state, effective_batch_size
                    )
                except Exception as exc:
                    state["status"] = "failed"
                    state["error_summary"] = (
                        f"detail load failed: {type(exc).__name__}: {exc}"
                    )

        for state in dataset_results:
            if state["status"] == "failed":
                state["rows_inserted"] = 0
                state["rows_updated"] = 0
                state["rows_skipped"] = state.get("exact_duplicates", 0)
            elif dry_run:
                state["rows_inserted"] = 0
                state["rows_updated"] = 0
                state["rows_skipped"] = state.get("exact_duplicates", 0)
            else:
                _apply_asset_counts(
                    state,
                    state.get("asset_statuses", {}),
                    detail_statuses.get(state["dataset"], {}),
                )

        accepted_registry = {
            row["asset_id"]: row["asset_type"]
            for state in dataset_results
            for row in state.get("asset_rows", [])
        }
        accepted_substations = {
            row["asset_id"]
            for state in dataset_results
            if state["dataset"] == "substations"
            for row in state.get("asset_rows", [])
        }
        dependent_registry = (
            registry if dry_run else (accepted_registry if assets_loaded else {})
        )
        dependent_substations = (
            substation_ids if dry_run else (accepted_substations if assets_loaded else set())
        )

        for dataset in DEPENDENT_DATASETS:
            result = _stream_dependent_dataset(
                dataset,
                input_path,
                dependent_registry,
                dependent_substations,
                rejected,
                session_factory,
                effective_batch_size,
                dry_run,
            )
            dataset_results.append(result)

    # Persist observability for every dataset that produced a result.
    if not dry_run and run_row_created:
        assert session_factory is not None
        for result in dataset_results:
            try:
                _persist_observability(session_factory, run_id, result)
            except Exception as exc:
                result["status"] = "failed"
                message = f"observability persistence failed: {type(exc).__name__}: {exc}"
                result["error_summary"] = (
                    f"{result['error_summary']}; {message}"
                    if result["error_summary"]
                    else message
                )

    total_read = sum(item["rows_read"] for item in dataset_results)
    total_inserted = sum(item["rows_inserted"] for item in dataset_results)
    total_updated = sum(item["rows_updated"] for item in dataset_results)
    total_skipped = sum(item["rows_skipped"] for item in dataset_results)
    total_rejected = sum(item["rows_rejected"] for item in dataset_results)
    failed_datasets = [item["dataset"] for item in dataset_results if item["status"] == "failed"]

    if fatal_error or failed_datasets:
        status = "failed"
    elif dry_run:
        status = "dry_run"
    elif fail_on_rejected and total_rejected:
        status = "failed"
    elif total_rejected:
        status = "completed_with_rejections"
    else:
        status = "completed"

    error_parts = []
    if fatal_error:
        error_parts.append(fatal_error)
    for item in dataset_results:
        if item["error_summary"]:
            error_parts.append(f"{item['dataset']}: {item['error_summary']}")
    error_summary = "\n".join(error_parts) if error_parts else None

    report_path = report_path_dir / f"{run_id}.json"
    try:
        relative_report = report_path.resolve().relative_to(PROJECT_ROOT)
        report_path_display = str(relative_report)
    except ValueError:
        report_path_display = report_path.name

    try:
        input_dir_display = str(input_path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        input_dir_display = str(input_path)

    public_datasets = []
    for item in dataset_results:
        public = {
            key: value
            for key, value in item.items()
            if key not in {"asset_rows", "detail_rows", "asset_statuses", "exact_duplicates"}
            and not key.startswith("_")
        }
        public["duplicate_rows"] = item.get("exact_duplicates", 0)
        public_datasets.append(public)

    report: dict[str, Any] = {
        "run_id": str(run_id),
        "source_name": "synthetic_csv_bundle",
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "status": status,
        "dry_run": dry_run,
        "destination": destination,
        "input_dir": input_dir_display,
        "batch_size": effective_batch_size,
        "totals": {
            "datasets": len(dataset_results),
            "rows_read": total_read,
            "rows_inserted": total_inserted,
            "rows_updated": total_updated,
            "rows_skipped": total_skipped,
            "rows_rejected": total_rejected,
            "validation_errors": sum(
                item["validation_errors"] for item in dataset_results
            ),
            "validation_warnings": sum(
                item["validation_warnings"] for item in dataset_results
            ),
        },
        "datasets": public_datasets,
        "rejected_count": len(rejected),
        "error_summary": error_summary,
        "report_path": report_path_display,
    }

    if not dry_run and run_row_created:
        assert session_factory is not None
        try:
            with session_factory() as session, session.begin():
                run = session.get(IngestionRun, run_id)
                if run is not None:
                    run.completed_at = _utc_now()
                    run.status = status
                    run.rows_read = total_read
                    run.rows_inserted = total_inserted
                    run.rows_updated = total_updated
                    run.rows_skipped = total_skipped
                    run.rows_rejected = total_rejected
                    run.error_summary = error_summary
                    run.report_path = report_path_display
        except Exception as exc:
            report["error_summary"] = (
                f"{report['error_summary']}; run finalization failed: {type(exc).__name__}: {exc}"
                if report["error_summary"]
                else f"run finalization failed: {type(exc).__name__}: {exc}"
            )
            report["status"] = "failed"

        try:
            report["database_row_counts"] = _database_counts(session_factory)
        except Exception as exc:
            report["database_row_counts"] = {"error": f"{type(exc).__name__}: {exc}"}

    report["completed_at"] = _utc_now().isoformat()
    rejected_path = rejected_path_dir / f"{run_id}.json"
    try:
        report["rejected_path"] = str(rejected_path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        report["rejected_path"] = rejected_path.name
    report["report_path"] = report_path_display
    write_ingestion_report(report, report_path_dir)
    write_rejected_rows(str(run_id), rejected, rejected_path_dir)

    if engine is not None:
        engine.dispose()
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Validate and ingest synthetic GridOps CSVs into PostgreSQL."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-rejected", action="store_true")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--rejected-dir", type=Path, default=DEFAULT_REJECTED_DIR)
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional SQLAlchemy URL override. Credentials are never printed.",
    )
    args = parser.parse_args(argv)

    report = run_ingestion(
        input_dir=args.input_dir,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        fail_on_rejected=args.fail_on_rejected,
        report_dir=args.report_dir,
        rejected_dir=args.rejected_dir,
        database_url=args.database_url,
    )

    print(f"Run ID: {report['run_id']}")
    print(f"Status: {report['status']}")
    print(f"Destination: {report['destination']}")
    print(
        "Totals: read={rows_read} inserted={rows_inserted} updated={rows_updated} "
        "skipped={rows_skipped} rejected={rows_rejected}".format(**report["totals"])
    )
    for dataset in report["datasets"]:
        print(
            f"  {dataset['dataset']}: read={dataset['rows_read']} "
            f"inserted={dataset['rows_inserted']} updated={dataset['rows_updated']} "
            f"skipped={dataset['rows_skipped']} rejected={dataset['rows_rejected']} "
            f"status={dataset['status']}"
        )
    print(f"Report: {report['report_path']}")
    print(f"Rejected: {report['rejected_path']}")
    if report.get("error_summary"):
        print(f"Errors: {report['error_summary']}")
    return 0 if report["status"] in {"completed", "completed_with_rejections", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
