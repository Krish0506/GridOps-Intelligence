"""Static asset features.

Source: ``assets`` (unified dimension).  Type-specific detail tables
(``transformer_details``, ``substation_details``, ``circuit_breaker_details``,
``feeder_details``) are intentionally not flattened here: the milestone needs
leakage-safe, reusable features, and those detail rows are current-state
attributes without historical versions.

``operating_hours_cumulative`` on the asset row is a *current* snapshot with no
effective timestamp, so it is not emitted as a static feature.  A historical
operating-hours value is derived from telemetry at the cutoff instead (see
:mod:`ml.features.telemetry`).
"""

from __future__ import annotations

from datetime import datetime

from ml.features.cutoff import normalize_timestamp
from ml.features.types import AssetRecord


def static_asset_features(asset: AssetRecord, prediction_cutoff: datetime) -> dict[str, object]:
    """Return deterministic static features for one asset at a cutoff.

    ``asset_age_days`` is ``None`` when the installation date is on or after the
    cutoff, because the asset did not exist yet at prediction time.  This avoids
    emitting a negative or future-derived age.

    ``asset_status`` is a *current-state* attribute (there is no historical
    status table) and is emitted only for traceability; it is classified as
    metadata and is excluded from the model feature contract.
    ``asset_region`` is treated as stable context for the observation period and
    is exposed as a categorical feature.
    """
    cutoff = normalize_timestamp(prediction_cutoff)
    installed_before_cutoff = asset.install_date is not None and asset.install_date < cutoff.date()

    if installed_before_cutoff and asset.install_date is not None:
        age_days: int | None = (
            cutoff.date() - asset.install_date
        ).days
    else:
        age_days = None

    return {
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "asset_name": asset.name,
        "asset_status": asset.status,
        "asset_region": asset.region,
        "asset_install_date": asset.install_date,
        "asset_installed_before_cutoff": installed_before_cutoff,
        "asset_age_days": age_days,
    }


def static_feature_names() -> list[str]:
    """Ordered feature names produced by :func:`static_asset_features`."""
    return [
        "asset_id",
        "asset_type",
        "asset_name",
        "asset_status",
        "asset_region",
        "asset_install_date",
        "asset_installed_before_cutoff",
        "asset_age_days",
    ]
