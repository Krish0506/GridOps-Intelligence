"""Independent synthetic evaluation-data generation (Milestone 2B).

This module creates a second, independent synthetic evaluation dataset whose
future failure events are driven by hidden degradation / stress processes.

Design rules implemented here (all of them auditable and deterministic):

* Failures are produced by an independent hidden degradation mechanism.  The
  ``compute_risk`` function from :mod:`data_engineering.generators.telemetry` is
  deliberately not used, so evaluation labels are independent of observable
  features.
* Historical telemetry is generated as noisy observations of the hidden
  degradation process; it never contains post-failure information.
* Corrective maintenance is not generated from future failure labels; only
  preventive / scheduled work orders are emitted, from independent draws.
* Inspections and weather are generated independently of failure outcomes.
* Labels use the Milestone 2A three-state contract via
  :func:`ml.features.labels.classify_outcomes`.

The output directory is separate from the Milestone 1 dataset
(``data/generated``) and defaults to ``data/evaluation``.
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from data_engineering.generators.base import (
    asset_id,
    iso_ts,
    load_rows,
    parse_ts,
    write_csv,
    write_json,
)
from data_engineering.generators.config import (
    ASSET_ID_FIELDS,
    ASSET_TABLES,
    BASE_TEMPERATURE,
    CATEGORY_BY_ASSET_TYPE,
    INSPECTION_CONDITIONS,
    INSPECTION_SEVERITIES,
    PRIORITIES,
    PROJECT_ROOT,
    REFERENCE_DATE,
    REGIONS,
    TABLE_FIELDNAMES,
    TELEMETRY_MISSING_FIELDS,
    TELEMETRY_MISSING_RATE,
    WEATHER_BASE_TEMPERATURES,
    WEATHER_OBSERVATIONS_RANGE,
    WORK_TYPES,
)
from data_engineering.generators.inspections import FINDINGS_BY_CONDITION, SEVERITY_BY_CONDITION
from data_engineering.generators.validation import validate_all
from ml.features.asset import build_asset_feature_record
from ml.features.labels import OutcomeLabel, classify_outcomes
from ml.features.types import (
    AssetRecord,
    FailureRecord,
    InspectionRecord,
    TelemetryReading,
    WeatherRecord,
    WorkOrderRecord,
    failure_from_mapping,
    inspection_from_mapping,
    telemetry_from_mapping,
    weather_from_mapping,
    work_order_from_mapping,
)

DEFAULT_INDEPENDENT_EVAL_SEED = 20261122
INDEPENDENT_EVAL_OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation"
DEFAULT_INDEPENDENT_ASSET_COUNT = 1500
INDEPENDENT_EVAL_OBSERVATION_DAYS = 365
INDEPENDENT_EVAL_HORIZON_DAYS = 90
INDEPENDENT_EVAL_FAILURE_PREVALENCE = 0.12


@dataclass(frozen=True)
class IndependentEvaluationParams:
    """Reproducible parameters for the independent evaluation dataset."""

    seed: int = DEFAULT_INDEPENDENT_EVAL_SEED
    asset_count: int = DEFAULT_INDEPENDENT_ASSET_COUNT
    observation_days: int = INDEPENDENT_EVAL_OBSERVATION_DAYS
    horizon_days: int = INDEPENDENT_EVAL_HORIZON_DAYS
    failure_prevalence: float = INDEPENDENT_EVAL_FAILURE_PREVALENCE


def _install_date(rng: random.Random, cutoff: datetime, observation_days: int) -> datetime:
    """Install date: complete-history assets end observation before cutoff."""
    complete_latest = cutoff - timedelta(days=observation_days)
    complete_earliest = complete_latest - timedelta(days=2 * observation_days)
    if rng.random() < 0.10:
        # Incomplete-history assets: installed inside the observation window.
        return cutoff - timedelta(days=rng.uniform(0, observation_days))
    return complete_earliest + timedelta(days=rng.uniform(0, max(1, int((complete_latest - complete_earliest).days))))


def _generate_independent_assets(
    rng: random.Random, params: IndependentEvaluationParams
) -> list[dict[str, str]]:
    """Generate a small independent synthetic asset population."""
    cutoff = REFERENCE_DATE - timedelta(days=params.observation_days)
    total = max(4, int(params.asset_count))
    substation_count = max(1, int(round(total * 0.20)))
    breaker_count = max(1, int(round(total * 0.20)))
    feeder_count = max(1, int(round(total * 0.20)))
    transformer_count = max(1, total - substation_count - breaker_count - feeder_count)

    assets: list[dict[str, str]] = []

    for i in range(1, substation_count + 1):
        assets.append(
            {
                ASSET_ID_FIELDS["substations"]: f"S-{i:05d}",
                "asset_type": "substations",
                "name": f"Independent Substation S-{i:03d}",
                "region": rng.choice(list(REGIONS)),
                "nominal_kv": str(rng.choice([115, 230, 345])),
                "area_sq_mi": str(rng.randrange(20, 900)),
                "equipment_count": str(rng.randrange(4, 40)),
                "install_date": iso_ts(_install_date(rng, cutoff, params.observation_days)),
                "operating_hours_cumulative": str(rng.randrange(0, 40000)),
                "status": "active" if rng.random() > 0.05 else "retired",
                "synthetic": "true",
            }
        )

    substation_ids = [row[ASSET_ID_FIELDS["substations"]] for row in assets]

    for i in range(1, breaker_count + 1):
        assets.append(
            {
                ASSET_ID_FIELDS["circuit_breakers"]: f"CB-{i:05d}",
                "asset_type": "circuit_breakers",
                "name": f"Independent Breaker CB-{i:04d}",
                "substation_id": rng.choice(substation_ids),
                "panel_id": f"PAN-{i:04d}",
                "region": rng.choice(list(REGIONS)),
                "rated_current_a": str(rng.choice([125, 250, 400, 630, 1000])),
                "voltage_class": rng.choice(["115kV", "138kV", "230kV", "345kV"]),
                "install_date": iso_ts(_install_date(rng, cutoff, params.observation_days)),
                "operating_hours_cumulative": str(rng.randrange(0, 12000)),
                "status": "active",
                "synthetic": "true",
            }
        )

    for i in range(1, feeder_count + 1):
        assets.append(
            {
                ASSET_ID_FIELDS["feeders"]: f"F-{i:05d}",
                "asset_type": "feeders",
                "name": f"Independent Feeder F-{i:04d}",
                "substation_id": rng.choice(substation_ids),
                "region": rng.choice(list(REGIONS)),
                "voltage_kv": str(rng.choice([4.16, 12.5, 13.8])),
                "capacity_kva": str(rng.choice([500, 1000, 2000, 4000, 8000])),
                "length_km": str(round(rng.uniform(1.0, 40.0), 1)),
                "outage_count": str(rng.randrange(0, 8)),
                "install_date": iso_ts(_install_date(rng, cutoff, params.observation_days)),
                "operating_hours_cumulative": str(rng.randrange(0, 10000)),
                "status": "active",
                "synthetic": "true",
            }
        )

    for i in range(1, transformer_count + 1):
        assets.append(
            {
                ASSET_ID_FIELDS["transformers"]: f"T-{i:05d}",
                "asset_type": "transformers",
                "name": f"Independent Transformer T-{i:04d}",
                "substation_id": rng.choice(substation_ids),
                "region": rng.choice(list(REGIONS)),
                "winding_type": rng.choice(["Dyn11", "Yd11", "Dyn5"]),
                "rating_mva": str(rng.choice([5, 10, 25, 50, 100, 200])),
                "primary_kv": str(rng.choice([115, 138, 230, 345])),
                "secondary_kv": str(rng.choice([13.8, 34.5, 4.16, 6.6])),
                "install_date": iso_ts(_install_date(rng, cutoff, params.observation_days)),
                "operating_hours_cumulative": str(rng.randrange(0, 50000)),
                "status": "active" if rng.random() > 0.05 else "retired",
                "synthetic": "true",
            }
        )
    return assets


def _independent_voltage_kv(rng: random.Random, asset: dict[str, str]) -> float:
    """Realistic nominal-ish operating voltage for an independent asset."""
    if asset["asset_type"] == "transformers":
        return round(rng.uniform(float(asset["primary_kv"]) * 0.98, float(asset["primary_kv"]) * 1.02), 2)
    if asset["asset_type"] == "substations":
        return round(rng.uniform(float(asset["nominal_kv"]) * 0.98, float(asset["nominal_kv"]) * 1.02), 2)
    if asset["asset_type"] == "circuit_breakers":
        return round(float(asset["voltage_class"].replace("kV", "").replace(" ", "")), 2)
    return round(rng.uniform(float(asset.get("voltage_kv") or 10) * 0.98, float(asset.get("voltage_kv") or 10) * 1.02), 2)


def _generate_independent_telemetry(
    rng: random.Random,
    assets: list[dict[str, str]],
    cutoff: datetime,
    params: IndependentEvaluationParams,
    failures_by_asset: dict[str, datetime],
) -> list[dict[str, str]]:
    """Generate noisy historical telemetry from the hidden degradation process."""
    rows: list[dict[str, str]] = []
    for asset in assets:
        aid = asset_id(asset)
        install = parse_ts(asset.get("install_date") or "") or cutoff
        window_start = min(cutoff - timedelta(days=params.observation_days), install)
        if window_start >= cutoff:
            continue
        failure_time = failures_by_asset.get(aid)
        failure_elapsed_days: float | None = None
        elapsed_cap_days = (cutoff - window_start).total_seconds() / 86400.0
        if failure_time is not None:
            failure_elapsed_days = (failure_time - window_start).total_seconds() / 86400.0
            elapsed_cap_days = min(elapsed_cap_days, (failure_time - window_start).total_seconds() / 86400.0)
        asset_type = asset["asset_type"]
        base_temp = BASE_TEMPERATURE[asset_type]
        base_load = {"transformers": 70.0, "substations": 50.0, "circuit_breakers": 60.0, "feeders": 60.0}[asset_type]
        base_vib = {"transformers": 1.0, "substations": 0.8, "circuit_breakers": 0.8, "feeders": 1.5}[asset_type]
        voltage_kv = _independent_voltage_kv(rng, asset)
        hours_base = float(asset.get("operating_hours_cumulative") or 0)
        n_samples = rng.randint(8, 20)
        for _ in range(n_samples):
            elapsed_days = rng.uniform(0.0, max(elapsed_cap_days, 1e-6))
            ts = window_start + timedelta(days=elapsed_days)
            degradation = min(1.0, elapsed_days / failure_elapsed_days) if failure_elapsed_days else rng.uniform(0.0, 0.1)
            temperature = round(base_temp + degradation * 30.0 + rng.uniform(-2.0, 2.0), 2)
            load_pct = round(min(130.0, base_load * (1.0 + 0.25 * degradation) + rng.uniform(-5.0, 5.0)), 2)
            vibration = round(base_vib + degradation * 4.0 + rng.uniform(0.0, 0.5), 3)
            current = round(max(0.0, min(6000.0, load_pct / 100.0 * voltage_kv * 1.73)), 1)
            hours = max(0.0, hours_base - elapsed_days * 24.0)
            row: dict[str, str] = {
                "asset_id": aid,
                "asset_type": asset_type,
                "timestamp": iso_ts(ts),
                "temperature_c": str(temperature),
                "load_pct": str(load_pct),
                "voltage_kv": str(round(voltage_kv, 2)),
                "current_a": str(current),
                "vibration_mm_s": str(vibration),
                "operating_hours_cumulative": str(int(hours)),
                "synthetic": "true",
            }
            if rng.random() < TELEMETRY_MISSING_RATE:
                row[rng.choice(TELEMETRY_MISSING_FIELDS)] = ""
            rows.append(row)
    return rows


def _generate_independent_failures(
    rng: random.Random,
    assets: list[dict[str, str]],
    cutoff: datetime,
    horizon_end: datetime,
    params: IndependentEvaluationParams,
) -> tuple[list[dict[str, str]], dict[str, datetime]]:
    """Generate future failures from the independent hidden degradation process."""
    rows: list[dict[str, str]] = []
    failures_by_asset: dict[str, datetime] = {}
    counter = 0
    for asset in assets:
        aid = asset_id(asset)
        if rng.random() >= params.failure_prevalence:
            continue
        failure_time = min(cutoff + timedelta(days=rng.uniform(0.5, max(0.5, params.horizon_days))), horizon_end)
        counter += 1
        failures_by_asset[aid] = failure_time
        rows.append(
            {
                "failure_id": f"FAIL-{counter:05d}",
                "asset_ref": aid,
                "failure_category": rng.choice(CATEGORY_BY_ASSET_TYPE[asset["asset_type"]]),
                "failure_timestamp": iso_ts(failure_time),
                "failure_severity": str(rng.randint(1, 5)),
                "downtime_hours": str(round(rng.uniform(0, 480), 1)),
                "synthetic": "true",
            }
        )
    return rows, failures_by_asset


def _generate_independent_work_orders(
    rng: random.Random,
    assets: list[dict[str, str]],
    cutoff: datetime,
) -> list[dict[str, str]]:
    """Generate preventive / scheduled work orders from independent draws."""
    rows: list[dict[str, str]] = []
    counter = 0
    for asset in assets:
        if rng.random() >= 0.6:
            continue
        counter += 1
        opened = cutoff - timedelta(days=rng.uniform(5, 300))
        status = "completed" if rng.random() < 0.7 else rng.choice(["open", "in_progress"])
        completed_at = ""
        if status == "completed":
            remaining = max(1, int((cutoff - opened).days))
            completed_at = iso_ts(opened + timedelta(days=rng.uniform(1, min(90, remaining))))
        rows.append(
            {
                "work_order_id": f"WO-{counter:05d}",
                "asset_ref": asset_id(asset),
                "work_type": rng.choice(["preventive", "scheduled"]),
                "priority": rng.choice(PRIORITIES),
                "status": status,
                "opened_at": iso_ts(opened),
                "completed_at": completed_at,
                "synthetic": "true",
            }
        )
    return rows


def _generate_independent_inspections(
    rng: random.Random,
    assets: list[dict[str, str]],
    cutoff: datetime,
) -> list[dict[str, str]]:
    """Generate independent inspection history."""
    rows: list[dict[str, str]] = []
    counter = 0
    for asset in assets:
        for _ in range(rng.randint(0, 2)):
            counter += 1
            inspection_date = cutoff - timedelta(days=rng.uniform(1, 300))
            condition = rng.choice(list(INSPECTION_CONDITIONS))
            rows.append(
                {
                    "inspection_id": f"INSP-{counter:05d}",
                    "inspection_date": iso_ts(inspection_date),
                    "asset_ref": asset_id(asset),
                    "condition": condition,
                    "findings": rng.choice(FINDINGS_BY_CONDITION[condition]),
                    "severity": rng.choice(SEVERITY_BY_CONDITION[condition]),
                    "synthetic": "true",
                }
            )
    return rows


def _generate_independent_weather(
    rng: random.Random,
    cutoff: datetime,
    params: IndependentEvaluationParams,
) -> list[dict[str, str]]:
    """Generate historical weather observations per region."""
    rows: list[dict[str, str]] = []
    counter = 0
    for region in list(REGIONS):
        for _ in range(rng.randint(*WEATHER_OBSERVATIONS_RANGE)):
            counter += 1
            day_of_year = rng.randrange(0, 366)
            seasonal = 12.0 * math.sin(2 * math.pi * day_of_year / 365.0)
            temperature = round(WEATHER_BASE_TEMPERATURES[region] + seasonal + rng.uniform(-3, 3), 1)
            wind_speed = round(rng.uniform(0, 40) + (rng.uniform(0, 5) if day_of_year > 300 else 0), 1)
            precipitation = round(rng.uniform(0, 5), 1) if rng.random() < 0.8 else round(rng.uniform(10, 60), 1)
            severe = "true" if (precipitation >= 20 and wind_speed >= 25) or rng.random() < 0.03 else "false"
            timestamp = cutoff - timedelta(days=rng.uniform(1, params.observation_days), hours=rng.randrange(0, 24))
            rows.append(
                {
                    "weather_id": f"WX-{counter:05d}",
                    "region": region,
                    "timestamp": iso_ts(timestamp),
                    "temperature_c": str(temperature),
                    "wind_speed_ms": str(wind_speed),
                    "precipitation_mm": str(precipitation),
                    "severe": severe,
                    "synthetic": "true",
                }
            )
    return rows


def generate_independent_evaluation(
    output_dir: Path | str | None = None,
    *,
    params: IndependentEvaluationParams | None = None,
) -> dict:
    """Generate the independent synthetic evaluation dataset and its manifest."""
    p = params or IndependentEvaluationParams()
    rng = random.Random(p.seed)
    output = Path(output_dir) if output_dir is not None else INDEPENDENT_EVAL_OUTPUT_DIR
    cutoff = REFERENCE_DATE - timedelta(days=p.observation_days)
    horizon_end = cutoff + timedelta(days=p.horizon_days)

    assets = _generate_independent_assets(rng, p)
    failures, failures_by_asset = _generate_independent_failures(rng, assets, cutoff, horizon_end, p)
    telemetry = _generate_independent_telemetry(rng, assets, cutoff, p, failures_by_asset)
    work_orders = _generate_independent_work_orders(rng, assets, cutoff)
    inspections = _generate_independent_inspections(rng, assets, cutoff)
    weather = _generate_independent_weather(rng, cutoff, p)

    datasets = [
        ("transformers", [a for a in assets if a["asset_type"] == "transformers"]),
        ("substations", [a for a in assets if a["asset_type"] == "substations"]),
        ("circuit_breakers", [a for a in assets if a["asset_type"] == "circuit_breakers"]),
        ("feeders", [a for a in assets if a["asset_type"] == "feeders"]),
        ("asset_telemetry", telemetry),
        ("work_orders", work_orders),
        ("inspections", inspections),
        ("failures", failures),
        ("weather", weather),
    ]
    files: dict[str, dict] = {}
    for name, rows in datasets:
        write_csv(output / f"{name}.csv", rows, list(TABLE_FIELDNAMES[name]))
        files[name] = {"path": f"{name}.csv", "rows": len(rows)}

    counts = {name: files[name]["rows"] for name in files}
    results = validate_all(output)

    failure_records: list[FailureRecord] = []
    for row in failures:
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failure_records.append(failure_from_mapping(mapped))
    asset_ids = [asset_id(asset) for asset in assets]
    confirmed_healthy_until: dict[str, datetime] = {}
    for asset in assets:
        aid = asset_id(asset)
        if aid in failures_by_asset:
            continue
        install = parse_ts(asset.get("install_date") or "") or cutoff
        if install + timedelta(days=p.observation_days) <= cutoff:
            confirmed_healthy_until[aid] = horizon_end
    decisions = classify_outcomes(
        failure_records,
        asset_ids,
        cutoff,
        horizon_end,
        confirmed_healthy_until=confirmed_healthy_until,
    )
    label_distribution = {
        "confirmed_positive": sum(1 for d in decisions if d.label is OutcomeLabel.CONFIRMED_POSITIVE),
        "confirmed_negative": sum(1 for d in decisions if d.label is OutcomeLabel.CONFIRMED_NEGATIVE),
        "unknown": sum(1 for d in decisions if d.label is OutcomeLabel.UNKNOWN),
        "total": len(decisions),
    }

    manifest = {
        "name": "gridops-independent-synthetic-evaluation",
        "generator": "data_engineering.generators.independent_evaluation",
        "reference_date": REFERENCE_DATE.isoformat(),
        "seed": p.seed,
        "params": {
            "asset_count": p.asset_count,
            "observation_days": p.observation_days,
            "horizon_days": p.horizon_days,
            "failure_prevalence": p.failure_prevalence,
        },
        "prediction_cutoff": cutoff.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "counts": counts,
        "total_assets": len(assets),
        "files": files,
        "label_distribution": label_distribution,
        "validation": {
            table: {
                "ok": result.ok,
                "errors": len(result.errors),
                "missing_fields": len(result.missing_fields),
                "duplicates": len(result.duplicates),
                "completeness": round(result.completeness, 4),
            }
            for table, result in results.items()
        },
        "synthetic": (
            "Independent synthetic evaluation data. No real utility or operational data is "
            "included; failures follow hidden degradation processes independent of observable risk."
        ),
        "notes": [
            "Independent synthetic evaluation data; generated by GridOps Intelligence "
            "data_engineering.generators.independent_evaluation.",
            "No DTE confidential or operational data is used.",
            "Failure labels follow hidden degradation processes independent of observable features.",
            "Historical telemetry precedes failure events and never contains post-failure data.",
        ],
    }
    manifest_path = output / "synthetic_manifest.json"
    write_json(manifest_path, manifest)
    files["synthetic_manifest"] = {"path": manifest_path.name, "rows": 0}
    return manifest


def build_independent_feature_snapshots(
    output_dir: Path | str | None = None,
    *,
    prediction_cutoff: datetime,
    horizon_days: int = INDEPENDENT_EVAL_HORIZON_DAYS,
) -> list[dict[str, object]]:
    """Build leakage-safe feature records from the independent evaluation data."""
    directory = Path(output_dir) if output_dir is not None else INDEPENDENT_EVAL_OUTPUT_DIR
    horizon_end = prediction_cutoff + timedelta(days=horizon_days)

    assets: list[AssetRecord] = []
    for table in ASSET_TABLES:
        id_field = ASSET_ID_FIELDS[table]
        for row in load_rows(directory / f"{table}.csv"):
            install = parse_ts(row.get("install_date") or "")
            assets.append(
                AssetRecord(
                    asset_id=str(row[id_field]),
                    asset_type=str(row["asset_type"]),
                    name=row.get("name") or None,
                    install_date=install.date() if install is not None else None,
                    status=row.get("status") or None,
                    region=row.get("region") or None,
                    operating_hours_cumulative=int(float(row.get("operating_hours_cumulative") or 0)),
                )
            )

    telemetry_readings = [telemetry_from_mapping(row) for row in load_rows(directory / "asset_telemetry.csv")]
    work_orders: list[WorkOrderRecord] = []
    for row in load_rows(directory / "work_orders.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        work_orders.append(work_order_from_mapping(mapped))
    inspections: list[InspectionRecord] = []
    for row in load_rows(directory / "inspections.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        inspections.append(inspection_from_mapping(mapped))
    weather_observations = [weather_from_mapping(row) for row in load_rows(directory / "weather.csv")]
    failures = []
    for row in load_rows(directory / "failures.csv"):
        mapped = dict(row)
        mapped["asset_id"] = mapped.get("asset_ref") or ""
        failures.append(failure_from_mapping(mapped))

    event_bounds: dict[str, datetime] = {failure.asset_id: failure.failure_timestamp for failure in failures}
    return [
        build_asset_feature_record(
            asset,
            telemetry_readings=telemetry_readings,
            work_orders=work_orders,
            inspections=inspections,
            weather_observations=weather_observations,
            prediction_cutoff=prediction_cutoff,
            window_days=None,
            exclude_at_or_after=event_bounds,
        )
        for asset in sorted(assets, key=lambda asset: asset.asset_id)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the independent synthetic evaluation dataset.")
    parser.add_argument("--output", type=Path, default=INDEPENDENT_EVAL_OUTPUT_DIR, help="Output directory (default: data/evaluation)")
    parser.add_argument("--seed", type=int, default=DEFAULT_INDEPENDENT_EVAL_SEED)
    parser.add_argument("--asset-count", type=int, default=DEFAULT_INDEPENDENT_ASSET_COUNT)
    parser.add_argument("--observation-days", type=int, default=INDEPENDENT_EVAL_OBSERVATION_DAYS)
    parser.add_argument("--horizon-days", type=int, default=INDEPENDENT_EVAL_HORIZON_DAYS)
    parser.add_argument("--failure-prevalence", type=float, default=INDEPENDENT_EVAL_FAILURE_PREVALENCE)
    args = parser.parse_args()
    manifest = generate_independent_evaluation(
        args.output,
        params=IndependentEvaluationParams(
            seed=args.seed,
            asset_count=args.asset_count,
            observation_days=args.observation_days,
            horizon_days=args.horizon_days,
            failure_prevalence=args.failure_prevalence,
        ),
    )
    print(f"Output directory: {args.output.resolve()}")
    print(f"Seed: {manifest['seed']}")
    print(f"Counts: {manifest['counts']}")
    print(f"Label distribution: {manifest['label_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
