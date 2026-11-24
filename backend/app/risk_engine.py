"""Risk-workbench analytics and transparent prioritization rules.

Persisted :class:`RiskRecord` rows are the source of truth.  This module never
invents a score:

* ``model_probability`` is the output of the trained predictive classifier.
* ``anomaly_score`` is an unsupervised robust deviation magnitude (not a
  calibrated failure probability).
* ``criticality`` is a deterministic engineering-consequence tier derived from
  the asset's type-specific attributes.
* ``data_quality`` flags come from the persisted feature snapshot.

The review band is a triage rule over those independent measures.  It is not a
composite failure probability and the UI labels it as a review priority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    Asset,
    CircuitBreakerDetail,
    EngineeringDecision,
    FeederDetail,
    RiskRecord,
    SubstationDetail,
    TransformerDetail,
)

PRIORITY_ORDER = ("P1", "P2", "P3", "P4", "P5")
PRIORITY_LABELS = {
    "P1": "P1 · Immediate review",
    "P2": "P2 · High",
    "P3": "P3 · Elevated",
    "P4": "P4 · Monitor",
    "P5": "P5 · Routine",
}
CRITICALITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CRITICALITY_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
}

PRIORITY_RULES = [
    "P1: model-probability percentile ≥ 99 and (criticality is High/Critical or anomaly percentile ≥ 99).",
    "P2: model-probability percentile ≥ 95, or anomaly percentile ≥ 99 with High/Critical criticality.",
    "P3: model-probability percentile ≥ 80, or anomaly percentile ≥ 90.",
    "P4: model-probability percentile ≥ 50, or anomaly percentile ≥ 75.",
    "P5: all remaining assets.",
]


@dataclass(frozen=True)
class Criticality:
    tier: str
    score: int
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "label": CRITICALITY_LABELS[self.tier],
            "score": self.score,
            "reasons": list(self.reasons),
        }


def _tier_from_score(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def criticality_map(session: Session) -> dict[str, Criticality]:
    """Compute a deterministic criticality tier for every asset.

    The rules are intentionally simple and inspectable.  They are a synthetic
    demonstration of consequence screening, not a utility-standard
    criticality classification.
    """
    result: dict[str, Criticality] = {}
    for row in session.execute(
        select(
            TransformerDetail.asset_id,
            TransformerDetail.rating_mva,
            TransformerDetail.primary_kv,
        )
    ):
        rating = _as_float(row.rating_mva) or 0.0
        primary = _as_float(row.primary_kv) or 0.0
        score = 30
        reasons: list[str] = []
        if rating >= 600:
            score += 35
            reasons.append(f"{rating:g} MVA rating is in the highest synthetic band")
        elif rating >= 300:
            score += 25
            reasons.append(f"{rating:g} MVA rating is high")
        elif rating >= 100:
            score += 12
            reasons.append(f"{rating:g} MVA rating is medium")
        if primary >= 345:
            score += 30
            reasons.append(f"{primary:g} kV primary voltage is transmission-critical")
        elif primary >= 230:
            score += 22
            reasons.append(f"{primary:g} kV primary voltage is high")
        elif primary >= 115:
            score += 10
        result[row.asset_id] = Criticality(_tier_from_score(score), score, reasons)

    for row in session.execute(
        select(
            SubstationDetail.asset_id,
            SubstationDetail.nominal_kv,
            SubstationDetail.equipment_count,
        )
    ):
        nominal = _as_float(row.nominal_kv) or 0.0
        equipment = int(row.equipment_count or 0)
        score = 35
        reasons = []
        if nominal >= 500:
            score += 35
            reasons.append(f"{nominal:g} kV substation")
        elif nominal >= 230:
            score += 25
            reasons.append(f"{nominal:g} kV substation")
        elif nominal >= 115:
            score += 12
        if equipment >= 30:
            score += 25
            reasons.append(f"{equipment} connected equipment items")
        elif equipment >= 20:
            score += 15
            reasons.append(f"{equipment} connected equipment items")
        result[row.asset_id] = Criticality(_tier_from_score(score), score, reasons)

    for row in session.execute(
        select(
            CircuitBreakerDetail.asset_id,
            CircuitBreakerDetail.voltage_class,
            CircuitBreakerDetail.rated_current_a,
        )
    ):
        voltage = str(row.voltage_class or "")
        current = _as_float(row.rated_current_a) or 0.0
        score = 30
        reasons = []
        if voltage == "345kV":
            score += 35
            reasons.append("345 kV voltage class")
        elif voltage == "230kV":
            score += 25
            reasons.append("230 kV voltage class")
        elif voltage in {"138kV", "115kV"}:
            score += 12
        if current >= 3000:
            score += 25
            reasons.append(f"{current:g} A rated current")
        elif current >= 2000:
            score += 15
            reasons.append(f"{current:g} A rated current")
        result[row.asset_id] = Criticality(_tier_from_score(score), score, reasons)

    for row in session.execute(
        select(
            FeederDetail.asset_id,
            FeederDetail.capacity_kva,
            FeederDetail.voltage_kv,
            FeederDetail.outage_count,
        )
    ):
        capacity = _as_float(row.capacity_kva) or 0.0
        voltage = _as_float(row.voltage_kv) or 0.0
        outages = int(row.outage_count or 0)
        score = 30
        reasons = []
        if capacity >= 30000:
            score += 30
            reasons.append(f"{capacity:g} kVA capacity")
        elif capacity >= 15000:
            score += 20
            reasons.append(f"{capacity:g} kVA capacity")
        elif capacity >= 5000:
            score += 10
        if outages >= 8:
            score += 30
            reasons.append(f"{outages} prior outages")
        elif outages >= 5:
            score += 20
            reasons.append(f"{outages} prior outages")
        elif outages >= 3:
            score += 10
        if voltage >= 34.5:
            score += 8
        result[row.asset_id] = Criticality(_tier_from_score(score), score, reasons)

    return result


def _latest_risk_rows(session: Session) -> list[RiskRecord]:
    rows = session.scalars(
        select(RiskRecord).order_by(RiskRecord.prediction_cutoff.desc(), RiskRecord.id.desc())
    ).all()
    latest: dict[str, RiskRecord] = {}
    for row in rows:
        latest.setdefault(row.asset_id, row)
    return list(latest.values())


def _rank_percentile_map(
    rows: list[RiskRecord],
    value_getter,
    *,
    anomaly_getter=None,
) -> dict[str, float]:
    """Assign deterministic population percentiles (1.0 = most extreme).

    Many synthetic model probabilities are exactly 1.0, so a mid-rank
    percentile would cap the top band below 0.99.  Ties are therefore broken
    deterministically by the other risk measures before ranks are assigned.
    The ordering is documented in the API's priority rules.
    """
    def sort_key(row: RiskRecord):
        value = value_getter(row)
        anomaly = anomaly_getter(row) if anomaly_getter is not None else None
        return (
            value is None,
            -(value if value is not None else 0.0),
            -(anomaly if anomaly is not None else 0.0),
            row.asset_id,
        )

    ordered = sorted(rows, key=sort_key)
    denominator = max(1, len(ordered) - 1)
    return {
        row.asset_id: max(0.0, 1.0 - (index / denominator))
        for index, row in enumerate(ordered)
    }


def _quality_flags(data_quality: dict[str, Any] | None) -> list[str]:
    quality = data_quality or {}
    flags: list[str] = []
    if not bool(quality.get("telemetry_has_readings")):
        flags.append("No telemetry readings at the prediction cutoff")
    if bool(quality.get("telemetry_sparse")):
        flags.append("Sparse telemetry coverage")
    groups = int(quality.get("quality_history_group_count") or 0)
    if groups < 3:
        missing = 3 - groups
        flags.append(f"Missing {missing} of 3 history groups (maintenance, inspection, weather)")
    return flags


def _priority_band(
    model_percentile: float | None,
    anomaly_percentile: float | None,
    criticality: Criticality,
) -> str:
    critical = CRITICALITY_ORDER.get(criticality.tier, 0)
    probability_rank = model_percentile if model_percentile is not None else -1.0
    anomaly_rank = anomaly_percentile if anomaly_percentile is not None else -1.0
    if probability_rank >= 0.99 and (critical >= 3 or anomaly_rank >= 0.99):
        return "P1"
    if probability_rank >= 0.95 or (anomaly_rank >= 0.99 and critical >= 3):
        return "P2"
    if probability_rank >= 0.80 or anomaly_rank >= 0.90:
        return "P3"
    if probability_rank >= 0.50 or anomaly_rank >= 0.75:
        return "P4"
    return "P5"


def build_risk_items(session: Session, *, asset_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Build enriched risk rows for every asset with a persisted risk record."""
    rows = _latest_risk_rows(session)
    if asset_ids is not None:
        wanted = set(asset_ids)
        rows = [row for row in rows if row.asset_id in wanted]
    if not rows:
        return []

    assets = {
        asset.asset_id: asset
        for asset in session.scalars(select(Asset)).all()
    }
    criticality = criticality_map(session)
    probabilities = {row.asset_id: _as_float(row.model_probability) for row in rows}
    anomalies = {row.asset_id: _as_float(row.anomaly_score) for row in rows}
    probability_percentiles = _rank_percentile_map(
        rows,
        lambda row: probabilities.get(row.asset_id),
        anomaly_getter=lambda row: anomalies.get(row.asset_id),
    )
    anomaly_percentiles = _rank_percentile_map(
        rows,
        lambda row: anomalies.get(row.asset_id),
        anomaly_getter=lambda row: probabilities.get(row.asset_id),
    )
    decisions_by_asset: dict[str, list[EngineeringDecision]] = {}
    for decision in session.scalars(select(EngineeringDecision)).all():
        decisions_by_asset.setdefault(decision.asset_id, []).append(decision)

    items: list[dict[str, Any]] = []
    for row in rows:
        asset = assets.get(row.asset_id)
        crit = criticality.get(row.asset_id, Criticality("low", 0, []))
        probability = probabilities.get(row.asset_id)
        anomaly = anomalies.get(row.asset_id)
        probability_percentile = probability_percentiles.get(row.asset_id)
        anomaly_percentile = anomaly_percentiles.get(row.asset_id)
        priority = _priority_band(probability_percentile, anomaly_percentile, crit)
        related = sorted(
            decisions_by_asset.get(row.asset_id, []),
            key=lambda item: item.created_at,
            reverse=True,
        )
        items.append(
            {
                "asset_id": row.asset_id,
                "asset_type": row.asset_type,
                "asset_name": asset.name if asset else None,
                "region": asset.region if asset else None,
                "status": asset.status if asset else None,
                "prediction_cutoff": row.prediction_cutoff.isoformat(),
                "risk_category": row.risk_category,
                "model_probability": probability,
                "model_probability_percentile": probability_percentile,
                "anomaly_score": anomaly,
                "anomaly_percentile": anomaly_percentile,
                "criticality": crit.as_dict(),
                "data_quality": row.data_quality or {},
                "data_quality_flags": _quality_flags(row.data_quality),
                "primary_drivers": list(row.primary_drivers or []),
                "model_version": row.model_version,
                "limitations": list(row.limitations or []),
                "review_priority": priority,
                "review_priority_label": PRIORITY_LABELS[priority],
                "decision_count": len(related),
                "latest_decision_status": related[0].decision_status if related else None,
                "latest_decision_id": str(related[0].decision_id) if related else None,
            }
        )

    items.sort(
        key=lambda item: (
            PRIORITY_ORDER.index(item["review_priority"]),
            -(item["model_probability"] or 0.0),
            -(item["anomaly_score"] or 0.0),
            item["asset_id"],
        )
    )
    for rank, item in enumerate(items, start=1):
        item["rank"] = rank
    return items


def filter_risk_items(
    items: list[dict[str, Any]],
    *,
    search: str | None = None,
    asset_type: str | None = None,
    priority: str | None = None,
    risk_category: str | None = None,
    sort: str = "rank",
    direction: str = "asc",
) -> list[dict[str, Any]]:
    """Apply server-side filters and sorting to enriched risk rows."""
    filtered = items
    if search and search.strip():
        term = search.strip().lower()
        filtered = [
            item
            for item in filtered
            if term in item["asset_id"].lower()
            or term in (item.get("asset_name") or "").lower()
        ]
    if asset_type:
        filtered = [item for item in filtered if item["asset_type"] == asset_type]
    if priority:
        filtered = [item for item in filtered if item["review_priority"] == priority]
    if risk_category:
        filtered = [item for item in filtered if item["risk_category"] == risk_category]

    sort_keys = {
        "rank": lambda item: item["rank"],
        "asset_id": lambda item: item["asset_id"],
        "model_probability": lambda item: item["model_probability"] if item["model_probability"] is not None else -1.0,
        "anomaly_score": lambda item: item["anomaly_score"] if item["anomaly_score"] is not None else -1.0,
        "criticality": lambda item: CRITICALITY_ORDER.get(item["criticality"]["tier"], 0),
        "prediction_cutoff": lambda item: item["prediction_cutoff"],
    }
    key = sort_keys.get(sort, sort_keys["rank"])
    reverse = direction.lower() == "desc"
    if sort == "rank":
        reverse = direction.lower() == "desc"
    return sorted(filtered, key=key, reverse=reverse)


def risk_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the full ranked population (never only the current page)."""
    by_priority = {band: 0 for band in PRIORITY_ORDER}
    by_type: dict[str, int] = {}
    by_category: dict[str, int] = {}
    criticality_counts: dict[str, int] = {tier: 0 for tier in CRITICALITY_ORDER}
    probability_buckets = {"0-0.05": 0, "0.05-0.2": 0, "0.2-0.5": 0, "0.5-0.9": 0, "0.9-1.0": 0, "unavailable": 0}
    data_quality_warning_count = 0
    model_versions: set[str] = set()
    cutoffs: set[str] = set()
    for item in items:
        by_priority[item["review_priority"]] = by_priority.get(item["review_priority"], 0) + 1
        by_type[item["asset_type"]] = by_type.get(item["asset_type"], 0) + 1
        by_category[item["risk_category"]] = by_category.get(item["risk_category"], 0) + 1
        criticality_counts[item["criticality"]["tier"]] += 1
        value = item["model_probability"]
        if value is None:
            probability_buckets["unavailable"] += 1
        elif value < 0.05:
            probability_buckets["0-0.05"] += 1
        elif value < 0.2:
            probability_buckets["0.05-0.2"] += 1
        elif value < 0.5:
            probability_buckets["0.2-0.5"] += 1
        elif value < 0.9:
            probability_buckets["0.5-0.9"] += 1
        else:
            probability_buckets["0.9-1.0"] += 1
        if item["data_quality_flags"]:
            data_quality_warning_count += 1
        if item["model_version"]:
            model_versions.add(item["model_version"])
        cutoffs.add(item["prediction_cutoff"])
    return {
        "total": len(items),
        "by_priority": by_priority,
        "by_type": by_type,
        "by_category": by_category,
        "criticality": criticality_counts,
        "probability_buckets": probability_buckets,
        "data_quality_warning_count": data_quality_warning_count,
        "model_versions": sorted(model_versions),
        "prediction_cutoffs": sorted(cutoffs),
        "priority_rules": PRIORITY_RULES,
        "top_assets": items[:6],
    }


__all__ = [
    "CRITICALITY_LABELS",
    "CRITICALITY_ORDER",
    "PRIORITY_LABELS",
    "PRIORITY_ORDER",
    "PRIORITY_RULES",
    "Criticality",
    "build_risk_items",
    "criticality_map",
    "filter_risk_items",
    "risk_summary",
]
