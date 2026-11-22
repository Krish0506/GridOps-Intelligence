"""Generators for asset telemetry: temperature, load, voltage, current,
vibration, and operating hours."""

from __future__ import annotations

import math
import random
from datetime import timedelta

from data_engineering.generators.base import iso_ts, parse_ts
from data_engineering.generators.config import (
    ASSET_ID_FIELDS,
    ABNORMAL_RANGES,
    BASE_TEMPERATURE,
    TELEMETRY_LOAD_RANGES,
    TELEMETRY_MAX_SAMPLES,
    TELEMETRY_MIN_SAMPLES,
    TELEMETRY_MISSING_FIELDS,
    TELEMETRY_MISSING_RATE,
    TELEMETRY_TEMPERATURE_RANGES,
    TELEMETRY_VIBRATION_RANGES,
    TELEMETRY_DUPLICATE_COUNT,
    REFERENCE_DATE,
)


def _voltage_kv(rng: random.Random, asset: dict[str, str]) -> float:
    """Realistic nominal-ish operating voltage for an asset."""
    if asset["asset_type"] == "transformers":
        return round(rng.uniform(float(asset["primary_kv"]) * 0.98, float(asset["primary_kv"]) * 1.02), 2)
    if asset["asset_type"] == "substations":
        return round(rng.uniform(float(asset["nominal_kv"]) * 0.98, float(asset["nominal_kv"]) * 1.02), 2)
    if asset["asset_type"] == "circuit_breakers":
        return round(float(asset["voltage_class"].replace("kV", "").replace(" ", "")), 2)
    return round(rng.uniform(float(asset["voltage_kv"]) * 0.98, float(asset["voltage_kv"]) * 1.02), 2)


def _current_a(rng: random.Random, asset: dict[str, str], load_pct: float, voltage_kv: float) -> float:
    """Realistic operating current for an asset."""
    if asset["asset_type"] == "transformers":
        current = float(asset["rating_mva"]) * 1_000_000 / (math.sqrt(3) * voltage_kv) * (load_pct / 100.0)
    elif asset["asset_type"] == "substations":
        current = rng.uniform(10, 250)
    elif asset["asset_type"] == "circuit_breakers":
        current = float(asset["rated_current_a"]) * (load_pct / 100.0)
    else:  # feeders
        current = float(asset["capacity_kva"]) / (voltage_kv * math.sqrt(3)) * (load_pct / 100.0)
    return max(0.0, min(5000.0, round(current + rng.uniform(-50, 50), 1)))


def _telemetry_row(rng: random.Random, asset: dict[str, str], timestamp=None) -> dict[str, str]:
    """Build one telemetry row for an asset within its normal ranges."""
    asset_type = asset["asset_type"]
    if timestamp is None:
        install = parse_ts(asset.get("install_date") or "") or REFERENCE_DATE
        horizon = max(1, int((REFERENCE_DATE - install).days))
        timestamp = install + timedelta(
            days=rng.randrange(horizon) if horizon > 1 else 0,
            hours=rng.randrange(0, 24),
            minutes=rng.randrange(0, 60),
        )
    voltage_kv = _voltage_kv(rng, asset)
    load_pct = round(rng.uniform(*TELEMETRY_LOAD_RANGES[asset_type]), 2)
    return {
        "asset_id": asset[ASSET_ID_FIELDS[asset_type]],
        "asset_type": asset_type,
        "timestamp": iso_ts(timestamp),
        "temperature_c": str(round(rng.uniform(*TELEMETRY_TEMPERATURE_RANGES[asset_type]), 2)),
        "load_pct": str(load_pct),
        "voltage_kv": str(round(voltage_kv, 2)),
        "current_a": str(_current_a(rng, asset, load_pct, voltage_kv)),
        "vibration_mm_s": str(round(rng.uniform(*TELEMETRY_VIBRATION_RANGES[asset_type]), 3)),
        "operating_hours_cumulative": str(
            max(0, int(asset["operating_hours_cumulative"]) - rng.randrange(0, 300))
        ),
        "synthetic": "true",
    }


def _abnormal_telemetry_row(rng: random.Random, asset: dict[str, str], timestamp=None) -> dict[str, str]:
    """Build one telemetry row with elevated readings, correlated with failure risk."""
    row = _telemetry_row(rng, asset, timestamp=timestamp)
    asset_type = asset["asset_type"]
    for field_name, value_range in ABNORMAL_RANGES[asset_type].items():
        row[field_name] = str(round(rng.uniform(*value_range), 3 if field_name == "vibration_mm_s" else 2))
    row["current_a"] = str(_current_a(rng, asset, float(row["load_pct"]), float(row["voltage_kv"])))
    return row


def compute_risk(rows: list[dict[str, str]], asset: dict[str, str]) -> float:
    """Derive a 0..1 failure-risk score from telemetry for an asset.

    Driven by vibration magnitude, temperature excess above the asset's base
    operating temperature, and sustained load. No labels or future failure data
    are used, so this score is leak-free by construction.
    """
    if not rows:
        return 0.0
    base_temp = BASE_TEMPERATURE[asset["asset_type"]]
    vibration = max(
        (float(r["vibration_mm_s"]) for r in rows if str(r["vibration_mm_s"]).strip()), default=0.0
    )
    temperature = max(
        (float(r["temperature_c"]) for r in rows if str(r["temperature_c"]).strip()),
        default=base_temp,
    )
    load = max((float(r["load_pct"]) for r in rows if str(r["load_pct"]).strip()), default=50.0)
    risk = 0.0
    risk += min(0.4, vibration / 10.0)
    risk += min(0.4, max(temperature - base_temp, 0.0) / 15.0)
    risk += min(0.2, max(load - 75.0, 0.0) / 25.0)
    return min(1.0, round(risk, 4))


def generate_telemetry(rng: random.Random, assets: list[dict[str, str]]) -> list[dict[str, str]]:
    """Generate telemetry samples for every asset within its normal ranges."""
    rows: list[dict[str, str]] = []
    for asset in assets:
        asset_type = asset["asset_type"]
        n_samples = rng.randint(TELEMETRY_MIN_SAMPLES[asset_type], TELEMETRY_MAX_SAMPLES[asset_type])
        for _ in range(n_samples):
            rows.append(_telemetry_row(rng, asset))
    # Controlled missing values: ~1% of telemetry rows have one field blanked.
    for row in rows:
        if rng.random() < TELEMETRY_MISSING_RATE:
            row[rng.choice(TELEMETRY_MISSING_FIELDS)] = ""
    # Controlled duplicates for data-quality testing.
    for _ in range(TELEMETRY_DUPLICATE_COUNT):
        if rows:
            rows.append(dict(rng.choice(rows)))
    return rows


def inject_abnormal_telemetry(
    rng: random.Random,
    assets_by_id: dict[str, dict[str, str]],
    failures: list[dict[str, str]],
    telemetry_rows: list[dict[str, str]],
) -> None:
    """Append elevated telemetry rows around each failure timestamp.

    Keeps failure labels out of the inputs: the elevated readings are the
    feature signal, and each row is appended only when the asset exists.
    """
    for failure in failures:
        asset = assets_by_id.get(failure["asset_ref"])
        if asset is None:
            continue
        failure_ts = parse_ts(failure["failure_timestamp"]) or REFERENCE_DATE
        for _ in range(rng.randrange(1, 4)):
            offset = timedelta(days=rng.randrange(-2, 3))
            timestamp = min(REFERENCE_DATE, failure_ts + offset)
            telemetry_rows.append(_abnormal_telemetry_row(rng, asset, timestamp=timestamp))
