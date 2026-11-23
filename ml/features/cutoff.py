"""Strict prediction-cutoff helpers.

Every feature function in this package takes an explicit ``prediction_cutoff``.
The semantics are deliberately strict: a record is usable only when its
timestamp is *strictly earlier* than the cutoff.  A record whose timestamp is
exactly equal to the cutoff is future information relative to the prediction
instant and is excluded.

Naive datetimes are the project convention (the fact tables use
``DateTime(timezone=False)``).  Aware datetimes are normalised to UTC and then
made naive so comparisons never raise on mixed inputs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import TypeVar

T = TypeVar("T")

# An event bound may be a single global datetime (the earliest failure observed
# for the batch) or a mapping of ``asset_id -> failure timestamp`` for assets
# that failed at different times.
EventBound = datetime | Mapping[str, datetime] | None


def resolve_event_bound(
    exclude_at_or_after: EventBound,
    asset_id: str,
) -> datetime | None:
    """Return the event bound that applies to one asset.

    A mapping of ``asset_id -> datetime`` is resolved per asset; a single
    datetime is shared by every asset in the call.  ``None`` means "no event
    bound", in which case only the prediction cutoff applies.
    """
    if exclude_at_or_after is None:
        return None
    if isinstance(exclude_at_or_after, Mapping):
        return exclude_at_or_after.get(asset_id)
    return exclude_at_or_after


def normalize_timestamp(value: datetime) -> datetime:
    """Return a naive UTC datetime for a naive or timezone-aware value."""
    if not isinstance(value, datetime):
        raise TypeError(f"expected datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def is_strictly_before(timestamp: datetime, cutoff: datetime) -> bool:
    """True when ``timestamp`` is strictly earlier than ``cutoff``."""
    return normalize_timestamp(timestamp) < normalize_timestamp(cutoff)


def filter_strictly_before(
    records: Iterable[T],
    cutoff: datetime,
    key: Callable[[T], datetime],
) -> list[T]:
    """Keep records whose key timestamp is strictly earlier than ``cutoff``."""
    bound = normalize_timestamp(cutoff)
    return [record for record in records if normalize_timestamp(key(record)) < bound]


def effective_bound(
    prediction_cutoff: datetime,
    exclude_at_or_after: datetime | None = None,
) -> datetime:
    """Combine the prediction cutoff with an optional event bound.

    ``exclude_at_or_after`` is used to drop telemetry at or after a known
    failure timestamp even when a later prediction cutoff is supplied.  The
    earlier of the two bounds wins.
    """
    bound = normalize_timestamp(prediction_cutoff)
    if exclude_at_or_after is not None:
        bound = min(bound, normalize_timestamp(exclude_at_or_after))
    return bound


def window_start(bound: datetime, window_days: int | float | None) -> datetime | None:
    """Return the inclusive start of an optional lookback window."""
    if window_days is None:
        return None
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    return bound - timedelta(days=float(window_days))


def is_within_window(
    timestamp: datetime,
    bound: datetime,
    window_days: int | float | None,
) -> bool:
    """True when the timestamp is before ``bound`` and inside the lookback window."""
    moment = normalize_timestamp(timestamp)
    if moment >= bound:
        return False
    start = window_start(bound, window_days)
    return start is None or moment >= start


def filter_window(
    records: Iterable[T],
    cutoff: datetime,
    key: Callable[[T], datetime],
    window_days: int | float | None = None,
    exclude_at_or_after: datetime | None = None,
) -> list[T]:
    """Filter records by strict cutoff, optional window, and optional event bound."""
    bound = effective_bound(cutoff, exclude_at_or_after)
    return [record for record in records if is_within_window(key(record), bound, window_days)]


def days_between(earlier: datetime, later: datetime) -> float:
    """Signed day difference (``later - earlier``) rounded to six decimals."""
    return round((normalize_timestamp(later) - normalize_timestamp(earlier)).total_seconds() / 86400.0, 6)


def sorted_by_time(records: Sequence[T], key: Callable[[T], datetime]) -> list[T]:
    """Stable sort by timestamp so duplicate timestamps keep their input order."""
    return sorted(records, key=lambda record: normalize_timestamp(key(record)))
