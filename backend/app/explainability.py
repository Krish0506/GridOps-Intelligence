"""Asset-level model explanation built from persisted features and artifacts.

The explanation deliberately uses the project's implemented methodology:

* robust z-score deviation of the asset's feature values from a population
  median/robust-scale baseline (``ml.anomaly``);
* global model feature importance derived from the trained model itself;
* the persisted prediction cutoff and data-quality flags.

It is **not** SHAP, does not estimate causal effects, and does not treat a
feature deviation as evidence that a failure will occur.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Asset, RiskRecord
from backend.app.risk_engine import Criticality, criticality_map
from backend.app.settings import (
    EXPLAINABILITY_DIR,
    artifact_version,
    model_artifact_path,
    safe_artifact_reference,
)
from ml.anomaly.detection import DEFAULT_Z_CAP, robust_z_scores
from ml.features.asset import model_feature_names
from ml.features.repository import build_feature_records_for_assets, load_failures
from ml.pipelines.inference import predict_positive_probability

BASELINE_PATH = EXPLAINABILITY_DIR / "baseline.json"

FEATURE_LABELS = {
    "asset_age_days": "Asset age (days)",
    "asset_installed_before_cutoff": "Installed before cutoff",
    "telemetry_reading_count": "Telemetry readings",
    "telemetry_distinct_timestamp_count": "Distinct telemetry timestamps",
    "telemetry_duplicate_timestamp_count": "Duplicate telemetry timestamps",
    "telemetry_missing_value_ratio": "Telemetry missing-value ratio",
    "telemetry_coverage_ratio": "Telemetry coverage ratio",
    "telemetry_days_since_last_reading": "Days since last reading",
    "telemetry_operating_hours_last": "Operating hours (last reading)",
    "maintenance_work_order_count": "Work-order count",
    "maintenance_orders_last_365_days": "Work orders (last 365 days)",
    "maintenance_preventive_count": "Preventive work orders",
    "maintenance_corrective_count": "Corrective work orders",
    "maintenance_open_count": "Open work orders",
    "maintenance_unresolved_count": "Unresolved work orders",
    "maintenance_mean_completion_days": "Mean completion days",
    "maintenance_days_since_last_completed": "Days since last completion",
    "inspection_count": "Inspection count",
    "inspection_count_last_365_days": "Inspections (last 365 days)",
    "inspection_days_since_last": "Days since last inspection",
    "inspection_latest_condition_score": "Latest condition score",
    "inspection_mean_severity_score": "Mean inspection severity",
    "weather_severe_count_last_30_days": "Severe weather events (30 days)",
    "weather_precipitation_mean_last_30_days": "Mean precipitation (30 days)",
    "quality_history_group_count": "History groups available",
    "quality_sensor_missing_count": "Sensors with missing values",
    "quality_sensors_observed_count": "Sensors observed",
}


def _friendly_name(name: str) -> str:
    if name in FEATURE_LABELS:
        return FEATURE_LABELS[name]
    return name.replace("_", " ").capitalize()


def _category_importance(group: str) -> str:
    return group.split("=")[0].split("__")[-1]


def global_feature_importance(model: Any, top_n: int = 15) -> list[dict[str, Any]]:
    """Aggregate model importance to original feature names.

    Logistic regression coefficients are measured on the fitted preprocessor's
    standardized/one-hot representation.  Tree importances come from the
    scikit-learn pipeline's transformed feature names.  Absolute magnitudes are
    normalized to sum to one; they describe model behaviour, not causality.
    """
    base_names = set(model_feature_names())
    grouped: dict[str, float] = {}

    if getattr(model, "sklearn_pipeline", None) is not None:
        pipeline = model.sklearn_pipeline
        preprocess = pipeline.named_steps.get("preprocess")
        estimator = pipeline.named_steps.get("model")
        importances = getattr(estimator, "feature_importances_", None)
        if preprocess is None or importances is None:
            return []
        transformed_names = [str(name) for name in preprocess.get_feature_names_out()]
        for name, value in zip(transformed_names, importances):
            cleaned = name.split("__", 1)[-1]
            group = cleaned
            for base in sorted(base_names, key=len, reverse=True):
                if cleaned == base or cleaned.startswith(base + "_"):
                    group = base
                    break
            grouped[group] = grouped.get(group, 0.0) + abs(float(value))
    elif getattr(model, "preprocessor", None) is not None and getattr(model, "weights", None):
        preprocessor = model.preprocessor
        weights = list(model.weights)
        index = 0
        for name in preprocessor.numeric_names:
            if index < len(weights):
                grouped[name] = grouped.get(name, 0.0) + abs(float(weights[index]))
            index += 1
        for name in preprocessor.categorical_names:
            width = len(preprocessor.categories.get(name, []))
            if index < len(weights):
                grouped[name] = grouped.get(name, 0.0) + sum(
                    abs(float(value)) for value in weights[index : index + width]
                )
            index += width
    else:
        return []

    total = sum(grouped.values())
    if total <= 0:
        return []
    ranked = sorted(grouped.items(), key=lambda item: item[1], reverse=True)[:top_n]
    return [
        {
            "feature": name,
            "label": _friendly_name(name),
            "importance": round(value / total, 6),
        }
        for name, value in ranked
    ]


def load_baseline() -> dict[str, Any] | None:
    """Load the persisted population baseline used for deviation scoring."""
    if not BASELINE_PATH.exists():
        return None
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _latest_risk(session: Session, asset_id: str) -> RiskRecord | None:
    return session.scalars(
        select(RiskRecord)
        .where(RiskRecord.asset_id == asset_id)
        .order_by(RiskRecord.prediction_cutoff.desc(), RiskRecord.id.desc())
        .limit(1)
    ).first()


def _load_model():
    from ml.artifacts.registry import load_model

    path = model_artifact_path("logistic_regression")
    if not path.exists():
        return None
    return load_model(path)


def explain_asset(session: Session, asset_id: str) -> dict[str, Any] | None:
    """Build one asset-level explanation, or ``None`` when prerequisites fail."""
    asset = session.get(Asset, asset_id)
    if asset is None:
        return None
    risk = _latest_risk(session, asset_id)
    if risk is None:
        return {
            "asset_id": asset_id,
            "unavailable": True,
            "reason": "No persisted risk record exists for this asset.",
        }

    model = _load_model()
    if model is None:
        return {
            "asset_id": asset_id,
            "unavailable": True,
            "reason": "No logistic regression artifact is available.",
        }

    cutoff = risk.prediction_cutoff
    failures = load_failures(session, [asset_id])
    first_failure = None
    for failure in failures:
        if failure.failure_timestamp < cutoff.replace(tzinfo=None):
            first_failure = failure.failure_timestamp
            break
    event_bound = {asset_id: first_failure} if first_failure is not None else None
    snapshots = build_feature_records_for_assets(
        session, [asset_id], cutoff, exclude_at_or_after=event_bound
    )
    if not snapshots:
        return {"asset_id": asset_id, "unavailable": True, "reason": "Feature snapshot could not be built."}
    snapshot = snapshots[0]

    baseline = load_baseline()
    if baseline is None:
        return {
            "asset_id": asset_id,
            "unavailable": True,
            "reason": "Population baseline artifact is missing. Run: python -m data_engineering.cli operational-risk --persist",
        }
    medians = {key: float(value) for key, value in (baseline.get("medians") or {}).items()}
    scales = {key: float(value) for key, value in (baseline.get("scales") or {}).items()}
    z_scores = robust_z_scores([snapshot], medians, scales)[0]
    probability = predict_positive_probability(model, snapshot)

    numeric_names = [name for name in model_feature_names() if name in medians]
    deviations: list[dict[str, Any]] = []
    missing: list[str] = []
    for name in numeric_names:
        value = snapshot.get(name)
        if value is None:
            missing.append(name)
            continue
        try:
            numeric_value = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        baseline_value = medians.get(name, 0.0)
        deviation = z_scores.get(name, 0.0)
        deviations.append(
            {
                "feature": name,
                "label": _friendly_name(name),
                "value": round(numeric_value, 6),
                "baseline": round(baseline_value, 6),
                "robust_z": round(float(deviation), 4),
                "direction": "above" if numeric_value >= baseline_value else "below",
            }
        )
    deviations.sort(key=lambda item: item["robust_z"], reverse=True)

    criticality = criticality_map(session).get(asset_id, Criticality("low", 0, []))
    data_quality = {
        "telemetry_has_readings": bool(snapshot.get("quality_telemetry_has_readings")),
        "telemetry_sparse": bool(snapshot.get("quality_telemetry_sparse")),
        "telemetry_coverage_ratio": snapshot.get("quality_telemetry_coverage_ratio"),
        "missing_value_ratio": snapshot.get("quality_telemetry_missing_value_ratio"),
        "history_group_count": int(snapshot.get("quality_history_group_count") or 0),
        "sensor_missing_count": int(snapshot.get("quality_sensor_missing_count") or 0),
        "sensors_observed_count": int(snapshot.get("quality_sensors_observed_count") or 0),
    }
    warnings: list[str] = []
    if not data_quality["telemetry_has_readings"]:
        warnings.append("No telemetry readings were available at the prediction cutoff.")
    if data_quality["telemetry_sparse"]:
        warnings.append("Telemetry coverage is sparse; the anomaly score may be less reliable.")
    if data_quality["history_group_count"] < 3:
        warnings.append("One or more maintenance, inspection, or weather history groups are missing.")
    if missing:
        warnings.append(f"{len(missing)} numeric model features were missing and imputed for the model.")

    return {
        "asset_id": asset_id,
        "asset_type": asset.asset_type,
        "asset_name": asset.name,
        "region": asset.region,
        "status": asset.status,
        "prediction_cutoff": cutoff.isoformat(),
        "event_bound": first_failure.isoformat() if first_failure else None,
        "model_name": model.model_name,
        "model_version": artifact_version("logistic_regression"),
        "model_threshold": float(getattr(model, "threshold", 0.5)),
        "probability": float(probability),
        "risk_category": risk.risk_category,
        "anomaly_score": float(risk.anomaly_score) if risk.anomaly_score is not None else None,
        "criticality": criticality.as_dict(),
        "top_deviations": deviations[:12],
        "all_deviation_count": len(deviations),
        "global_importance": global_feature_importance(model, top_n=12),
        "data_quality": data_quality,
        "warnings": warnings,
        "missing_features": missing,
        "methodology": {
            "deviation": "Robust z-score = |value − population median| / robust scale (MAD, IQR, or standard deviation fallback), capped at 50.",
            "importance": "Global importance is derived from the fitted model's coefficients or tree feature importances and aggregated to the original feature name.",
            "probability": "The probability is the trained classifier's synthetic-data output at the persisted prediction cutoff; it is not a calibrated field failure probability.",
            "causality": "Neither feature deviation nor global importance proves causation. Review engineering evidence before acting.",
        },
        "baseline_created_at": baseline.get("created_at"),
        "baseline_artifact": safe_artifact_reference(BASELINE_PATH),
        "z_cap": DEFAULT_Z_CAP,
    }


__all__ = [
    "BASELINE_PATH",
    "explain_asset",
    "global_feature_importance",
    "load_baseline",
]
