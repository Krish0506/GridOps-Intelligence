"""Generators for maintenance work orders."""

from __future__ import annotations

import random
from datetime import timedelta

from data_engineering.generators.base import asset_id, iso_ts, parse_ts
from data_engineering.generators.config import (
    PRIORITY_FROM_SEVERITY,
    REFERENCE_DATE,
    WORK_ORDER_DUPLICATE_COUNT,
)


def _remaining_days(opened_at: object) -> int:
    ts = parse_ts(str(opened_at)) if opened_at is not None else None
    if ts is None:
        return 1
    return max(0, int((REFERENCE_DATE - ts).days))


def generate_work_orders(
    rng: random.Random,
    assets: list[dict[str, str]],
    failures: list[dict[str, str]],
    risk_scores: dict[str, float],
) -> list[dict[str, str]]:
    """Generate work orders correlated with failures and asset risk."""
    asset_by_id = {asset_id(asset): asset for asset in assets}
    rows: list[dict[str, str]] = []
    counter = 0

    def _append(asset_ref: str, work_type: str, priority: str, status: str,
                opened_at: str, completed_at: str) -> None:
        nonlocal counter
        counter += 1
        rows.append(
            {
                "work_order_id": f"WO-{counter:05d}",
                "asset_ref": asset_ref,
                "work_type": work_type,
                "priority": priority,
                "status": status,
                "opened_at": opened_at,
                "completed_at": completed_at,
                "synthetic": "true",
            }
        )

    # Corrective orders triggered by failures.
    for failure in failures:
        if rng.random() > 0.5:
            continue
        asset = asset_by_id[failure["asset_ref"]]
        opened = parse_ts(failure["failure_timestamp"]) or REFERENCE_DATE
        severity = int(failure["failure_severity"])
        status = rng.choice(["open", "completed", "completed", "completed", "in_progress", "cancelled"])
        completed_at = ""
        if status == "completed":
            remaining = _remaining_days(opened)
            if remaining < 1:
                status = "in_progress"
            else:
                completed_at = iso_ts(opened + timedelta(days=rng.randrange(1, remaining + 1)))
        _append(asset_id(asset), "corrective", PRIORITY_FROM_SEVERITY[severity], status,
                iso_ts(opened), completed_at)

    # Preventive orders for high-risk assets that did not fail.
    for asset in assets:
        if risk_scores.get(asset_id(asset), 0.0) >= 0.6 and rng.random() < 0.5:
            opened = REFERENCE_DATE - timedelta(days=rng.randrange(60, 900))
            status = rng.choice(["completed", "completed", "open"])
            completed_at = ""
            if status == "completed":
                remaining = _remaining_days(opened)
                if remaining >= 1:
                    delay = rng.randrange(1, min(90, remaining) + 1)
                    completed_at = iso_ts(opened + timedelta(days=delay))
                else:
                    status = "open"
            _append(asset_id(asset), "preventive", "medium", status, iso_ts(opened), completed_at)

    # Scheduled orders spread across assets.
    sample_size = min(len(assets), 40 + int(len(assets) * 0.05))
    for asset in rng.sample(assets, sample_size):
        opened = REFERENCE_DATE - timedelta(days=rng.randrange(5, 400))
        status = rng.choice(["completed", "completed", "open"])
        completed_at = ""
        if status == "completed":
            remaining = _remaining_days(opened)
            if remaining < 1:
                status = "open"
            else:
                completed_at = iso_ts(opened + timedelta(days=rng.randrange(1, min(60, remaining) + 1)))
        _append(asset_id(asset), "scheduled", rng.choice(["low", "medium"]), status,
                iso_ts(opened), completed_at)

    # Controlled duplicates for data-quality testing.
    for _ in range(WORK_ORDER_DUPLICATE_COUNT):
        if rows:
            rows.append(dict(rng.choice(rows)))
    return rows
