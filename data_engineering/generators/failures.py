"""Generators for failure incidents."""

from __future__ import annotations

import random
from datetime import timedelta

from data_engineering.generators.base import asset_id, iso_ts, parse_ts
from data_engineering.generators.config import (
    CATEGORY_BY_ASSET_TYPE,
    FAILURE_COUNT,
    REFERENCE_DATE,
)
from data_engineering.generators.telemetry import compute_risk

_DOWNTIME_RANGES = {1: (0, 2), 2: (0, 12), 3: (8, 48), 4: (48, 240), 5: (96, 480)}


def _failure_severity(rng: random.Random) -> int:
    roll = rng.random()
    if roll < 0.10:
        return 1
    if roll < 0.25:
        return 2
    if roll < 0.45:
        return 3
    if roll < 0.80:
        return 4
    return 5


def _downtime_hours(rng: random.Random, severity: int) -> int:
    low, high = _DOWNTIME_RANGES[severity]
    return rng.randint(low, high)


def generate_failures(
    rng: random.Random,
    assets: list[dict[str, str]],
    telemetry_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, float]]:
    """Generate failure incidents, biased toward assets with elevated risk.

    Returns ``(failures, risk_scores)`` where ``risk_scores`` maps every asset id
    to a telemetry-derived risk (boosted for failed assets so downstream
    generators can correlate maintenance and inspections with risk).
    """
    by_asset: dict[str, list[dict[str, str]]] = {}
    for row in telemetry_rows:
        by_asset.setdefault(row["asset_id"], []).append(row)

    risk_scores = {asset_id(asset): compute_risk(by_asset.get(asset_id(asset), []), asset) for asset in assets}

    # Assets with the highest telemetry risk get the failures, the rest are
    # random. This encodes a realistic failure-risk concentration.
    candidates = sorted(assets, key=lambda a: risk_scores[asset_id(a)], reverse=True)
    selected = candidates[:FAILURE_COUNT] if len(candidates) > FAILURE_COUNT else candidates

    failures: list[dict[str, str]] = []
    for n, asset in enumerate(selected, start=1):
        ref = asset_id(asset)
        risk_scores[ref] = 0.75 + rng.random() * 0.25
        install = parse_ts(asset.get("install_date") or "") or REFERENCE_DATE
        horizon = max(1, int((REFERENCE_DATE - install).days))
        span_start = int(horizon * 0.6)
        failure_ts = min(REFERENCE_DATE, install + timedelta(days=rng.randrange(span_start, horizon)))
        severity = _failure_severity(rng)
        failures.append(
            {
                "failure_id": f"FAIL-{n:05d}",
                "asset_ref": ref,
                "failure_category": rng.choice(CATEGORY_BY_ASSET_TYPE[asset["asset_type"]]),
                "failure_timestamp": iso_ts(failure_ts),
                "failure_severity": str(severity),
                "downtime_hours": str(_downtime_hours(rng, severity)),
                "synthetic": "true",
            }
        )
    return failures, risk_scores
