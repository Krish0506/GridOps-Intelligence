"""Generators for asset inspections."""

from __future__ import annotations

import itertools
import random
from datetime import timedelta

from data_engineering.generators.base import asset_id, iso_ts
from data_engineering.generators.config import (
    INSPECTION_DUPLICATE_COUNT,
    INSPECTION_TARGET_COUNT,
    REFERENCE_DATE,
)

FINDINGS_BY_CONDITION = {
    "excellent": [
        "System operating normally. No corrective action required.",
        "Protective relays responding within expected time margins.",
        "Terminations and bushings clear of visible defects.",
        "Cooling fans, pumps, and ventilation equipment operating normally.",
        "Load, temperature, and vibration within expected ranges.",
    ],
    "good": [
        "Minor thermal gradient observed; well within acceptable limits.",
        "Insulation resistance slightly lower than baseline but adequate.",
        "No active complaints; findings consistent with normal operation.",
        "Contacts wear within specifications; torque verified to plan values.",
    ],
    "fair": [
        "Elevated temperature in substation bus area; recommend continued monitoring.",
        "Reduced insulation resistance on bushing 3; next scheduled inspection.",
        "Minor coolant system leakage observed during visual check.",
        "Load slightly above nominal; short-term trending is acceptable.",
    ],
    "poor": [
        "Significant thermal anomaly detected; operation above design limits.",
        "Bushing insulation resistance below threshold; recommend replacement window.",
        "Cooling system fan bearing failure suspected; production impact possible.",
        "Mechanical vibration outside operational envelope.",
        "Unexplained intermittent trip activity on this asset.",
    ],
}

SEVERITY_BY_CONDITION = {
    "excellent": ["none", "none"],
    "good": ["low", "none"],
    "fair": ["medium", "low", "none"],
    "poor": ["high", "medium", "low"],
}


def _condition_from_risk(rng: random.Random, risk: float) -> str:
    """Map a telemetry-derived risk score to an inspection condition."""
    if risk >= 0.6:
        return rng.choice(["poor", "poor", "fair"])
    if risk >= 0.35:
        return rng.choice(["fair", "good"])
    return rng.choice(["good", "excellent"])


def _inspection_row(rng: random.Random, asset: dict[str, str], risk: float, n: int) -> dict[str, str]:
    condition = _condition_from_risk(rng, risk)
    inspection_date = REFERENCE_DATE - timedelta(days=rng.randrange(0, 700))
    return {
        "inspection_id": f"INSP-{n:05d}",
        "inspection_date": iso_ts(inspection_date),
        "asset_ref": asset_id(asset),
        "condition": condition,
        "findings": rng.choice(FINDINGS_BY_CONDITION[condition]),
        "severity": rng.choice(SEVERITY_BY_CONDITION[condition]),
        "synthetic": "true",
    }


def generate_inspections(
    rng: random.Random,
    assets: list[dict[str, str]],
    risk_scores: dict[str, float],
) -> list[dict[str, str]]:
    """Generate inspections; high-risk assets are inspected more frequently."""
    counter = itertools.count(1)
    rows: list[dict[str, str]] = []

    target_assets = [a for a in assets if risk_scores.get(asset_id(a), 0.0) >= 0.6]
    for asset in target_assets:
        rows.append(_inspection_row(rng, asset, risk_scores[asset_id(asset)], next(counter)))

    target_ids = {asset_id(a) for a in target_assets}
    pool = [a for a in assets if asset_id(a) not in target_ids]
    rng.shuffle(pool)
    extras = pool[: max(0, INSPECTION_TARGET_COUNT - len(rows))]
    for asset in extras:
        rows.append(_inspection_row(rng, asset, risk_scores.get(asset_id(asset), 0.0), next(counter)))

    # Controlled duplicates for data-quality testing.
    for _ in range(INSPECTION_DUPLICATE_COUNT):
        if rows:
            rows.append(dict(rng.choice(rows)))
    return rows
