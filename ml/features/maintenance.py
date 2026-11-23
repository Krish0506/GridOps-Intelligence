"""Historical maintenance / work-order features.

Source: ``maintenance_work_orders``.  An order is eligible only when
``opened_at < prediction_cutoff``.

Only attributes that are *historically observable* at the cutoff are emitted:

* order count and work-type / priority breakdowns;
* completion durations, using ``completed_at`` only when it is strictly before
  the cutoff.

The source ``status`` column is a **current-state** value (it reflects the final
state of the order after any later workflow events).  It is therefore never used
to reconstruct historical open / in-progress / cancelled state, and the
status-specific historical features were removed.  An order that was opened
before the cutoff but not completed before the cutoff is reported through the
honest, historically observable ``maintenance_unresolved_at_cutoff_count`` flag
without claiming which lifecycle state it was in.

Failure severity and downtime are not available in this table and are never
consulted here.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import datetime

from ml.features.cutoff import days_between, filter_window, normalize_timestamp
from ml.features.types import WorkOrderRecord

WORK_TYPES: tuple[str, ...] = ("corrective", "preventive", "scheduled")
PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / float(denominator), 6)


def maintenance_features(
    work_orders: Iterable[WorkOrderRecord],
    prediction_cutoff: datetime,
    *,
    asset_id: str,
    exclude_at_or_after: datetime | None = None,
) -> dict[str, object]:
    """Aggregate work orders opened strictly before ``prediction_cutoff``.

    Parameters
    ----------
    work_orders:
        Work orders for a single asset (rows for other assets must already be
        filtered by the caller or by the asset-scoped builder).
    prediction_cutoff:
        Exclusive upper bound for order eligibility.
    asset_id:
        Asset identifier the rows are scoped to; rows for other assets are
        ignored.
    exclude_at_or_after:
        Optional event bound (typically the first known failure timestamp).
        Orders opened at or after the bound are excluded, so a pre-failure
        snapshot contains no post-failure maintenance context.
    """
    cutoff = normalize_timestamp(prediction_cutoff)
    scoped_orders = [order for order in work_orders if order.asset_id == asset_id]
    eligible = filter_window(
        scoped_orders,
        cutoff,
        key=lambda order: order.opened_at,
        exclude_at_or_after=exclude_at_or_after,
    )
    total = len(eligible)

    record: dict[str, object] = {
        "maintenance_work_order_count": total,
        "maintenance_has_history": total > 0,
        "maintenance_corrective_ratio": None,
        "maintenance_completed_before_cutoff_count": 0,
        "maintenance_completed_before_cutoff_ratio": None,
        "maintenance_unresolved_at_cutoff_count": 0,
        "maintenance_days_since_last_opened": None,
        "maintenance_days_since_last_completed": None,
        "maintenance_last_work_type": None,
        "maintenance_last_priority": None,
        "maintenance_mean_completion_days": None,
        "maintenance_median_completion_days": None,
        "maintenance_completion_duration_count": 0,
        "maintenance_orders_last_30_days": 0,
        "maintenance_orders_last_90_days": 0,
        "maintenance_orders_last_365_days": 0,
        "maintenance_high_priority_count": 0,
    }

    for work_type in WORK_TYPES:
        record[f"maintenance_{work_type}_count"] = 0
    for priority in PRIORITIES:
        record[f"maintenance_priority_{priority}_count"] = 0

    if not eligible:
        return record

    ordered = sorted(eligible, key=lambda order: normalize_timestamp(order.opened_at))
    last = ordered[-1]

    for work_type in WORK_TYPES:
        record[f"maintenance_{work_type}_count"] = sum(
            1 for order in ordered if order.work_type == work_type
        )
    for priority in PRIORITIES:
        record[f"maintenance_priority_{priority}_count"] = sum(
            1 for order in ordered if order.priority == priority
        )

    corrective = int(record["maintenance_corrective_count"])  # type: ignore[arg-type]
    completed = sum(
        1
        for order in ordered
        if order.completed_at is not None
        and normalize_timestamp(order.completed_at) < cutoff
    )
    record["maintenance_completed_before_cutoff_count"] = completed
    record["maintenance_completed_before_cutoff_ratio"] = _ratio(completed, total)
    record["maintenance_unresolved_at_cutoff_count"] = total - completed

    record["maintenance_corrective_ratio"] = _ratio(corrective, total)
    record["maintenance_high_priority_count"] = (
        int(record["maintenance_priority_high_count"])  # type: ignore[arg-type]
        + int(record["maintenance_priority_critical_count"])  # type: ignore[arg-type]
    )
    record["maintenance_days_since_last_opened"] = round(
        days_between(last.opened_at, cutoff), 6
    )
    record["maintenance_last_work_type"] = last.work_type
    record["maintenance_last_priority"] = last.priority

    completion_days = [
        days_between(order.opened_at, order.completed_at)
        for order in ordered
        if order.completed_at is not None
        and normalize_timestamp(order.completed_at) < cutoff
        and normalize_timestamp(order.completed_at) >= normalize_timestamp(order.opened_at)
    ]
    if completion_days:
        record["maintenance_completion_duration_count"] = len(completion_days)
        record["maintenance_mean_completion_days"] = round(
            statistics.fmean(completion_days), 6
        )
        record["maintenance_median_completion_days"] = round(
            statistics.median(completion_days), 6
        )

    completed_at_values = [
        normalize_timestamp(order.completed_at)
        for order in ordered
        if order.completed_at is not None
        and normalize_timestamp(order.completed_at) < cutoff
    ]
    if completed_at_values:
        record["maintenance_days_since_last_completed"] = round(
            days_between(max(completed_at_values), cutoff), 6
        )

    for days in (30, 90, 365):
        record[f"maintenance_orders_last_{days}_days"] = sum(
            1 for order in ordered if days_between(order.opened_at, cutoff) <= days
        )

    return record


def maintenance_feature_names() -> list[str]:
    """Ordered feature names produced by :func:`maintenance_features`."""
    names = [
        "maintenance_work_order_count",
        "maintenance_has_history",
        "maintenance_corrective_ratio",
        "maintenance_completed_before_cutoff_count",
        "maintenance_completed_before_cutoff_ratio",
        "maintenance_unresolved_at_cutoff_count",
        "maintenance_days_since_last_opened",
        "maintenance_days_since_last_completed",
        "maintenance_last_work_type",
        "maintenance_last_priority",
        "maintenance_mean_completion_days",
        "maintenance_median_completion_days",
        "maintenance_completion_duration_count",
        "maintenance_orders_last_30_days",
        "maintenance_orders_last_90_days",
        "maintenance_orders_last_365_days",
        "maintenance_high_priority_count",
    ]
    names.extend(f"maintenance_{work_type}_count" for work_type in WORK_TYPES)
    names.extend(f"maintenance_priority_{priority}_count" for priority in PRIORITIES)
    return names
