"""Model artifact inspection and evaluation summaries for the API."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from backend.app.settings import (
    DEFAULT_MODEL_NAME,
    EVALUATION_DIR,
    MODEL_LABELS,
    MODEL_NAMES,
    artifact_mtime,
    artifact_version,
    load_model_metadata,
    model_artifact_path,
    model_metadata_path,
    safe_artifact_reference,
)

METRIC_EXPLANATIONS = {
    "accuracy": "Share of held-out assets the model classified correctly. It can look high when one class dominates.",
    "precision": "Of the assets the model flagged as failures, the share that actually failed in the synthetic outcome window.",
    "recall": "Of the assets that actually failed in the synthetic outcome window, the share the model flagged.",
    "f1": "Harmonic mean of precision and recall; a single balanced summary of the flagging behaviour.",
    "roc_auc": "Probability that a randomly chosen failure is ranked above a randomly chosen non-failure. 0.5 is random; 1.0 is perfect separation.",
    "brier": "Mean squared error of the predicted probabilities. Lower is better; 0 is perfect calibration.",
    "average_precision": "Area under the precision-recall curve; useful when the failure class is rare.",
    "prevalence": "Share of confirmed failures in the evaluation cohort.",
}


def _load_metadata(model_name: str) -> dict[str, Any] | None:
    return load_model_metadata(model_name)


@lru_cache(maxsize=8)
def _load_model_cached(model_name: str, modified_ns: int, size: int):
    """Load each artifact at most once per process/file version."""
    path = model_artifact_path(model_name)
    if not path.exists():
        return None
    from ml.artifacts.registry import load_model

    try:
        return load_model(path)
    except Exception:  # noqa: BLE001 - never let a corrupt artifact crash the API
        return None


def _load_model_object(model_name: str):
    path = model_artifact_path(model_name)
    if not path.exists():
        return None
    stat = path.stat()
    return _load_model_cached(model_name, stat.st_mtime_ns, stat.st_size)


def _metric_block(metrics: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metrics:
        return None
    return {
        "accuracy": metrics.get("accuracy"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "f1": metrics.get("f1"),
        "brier": metrics.get("brier"),
        "roc_auc": metrics.get("roc_auc"),
        "average_precision": metrics.get("average_precision"),
        "prevalence": metrics.get("prevalence"),
        "confusion_matrix": metrics.get("confusion_matrix"),
    }


def model_summary(model_name: str) -> dict[str, Any]:
    """Return a complete, honest summary of one persisted model artifact."""
    path = model_artifact_path(model_name)
    meta = _load_metadata(model_name) or {}
    model = _load_model_object(model_name)
    available = path.exists() and model is not None
    validation_metrics = _metric_block(meta.get("metrics") or (getattr(model, "metrics", None) if model else None))
    test_metrics = _metric_block(
        (meta.get("test_metrics") if meta else None)
        or (getattr(model, "test_metrics", None) if model else None)
    )
    threshold = None
    if model is not None:
        threshold = getattr(model, "threshold", None)
    if threshold is None:
        threshold = meta.get("threshold")
    split = {
        "train_assets": len(getattr(model, "train_asset_ids", []) or []),
        "validation_assets": len(getattr(model, "validation_asset_ids", []) or []),
        "test_assets": len(getattr(model, "test_asset_ids", []) or []),
    } if model is not None else {}
    positive = getattr(model, "positive_count", None) if model is not None else meta.get("positive_count")
    negative = getattr(model, "negative_count", None) if model is not None else meta.get("negative_count")
    feature_names = getattr(model, "feature_names", None) if model is not None else meta.get("feature_names")
    return {
        "model_name": model_name,
        "label": MODEL_LABELS.get(model_name, model_name),
        "available": available,
        "model_version": artifact_version(model_name) if available else None,
        "artifact_path": safe_artifact_reference(path),
        "artifact_size_bytes": path.stat().st_size if path.exists() else None,
        "artifact_modified_at": artifact_mtime(path),
        "metadata_path": safe_artifact_reference(model_metadata_path(model_name)),
        "threshold": threshold,
        "feature_count": len(feature_names or []),
        "positive_count": positive,
        "negative_count": negative,
        "split": split,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "metric_explanations": METRIC_EXPLANATIONS,
        "evaluation_context": (
            "Trained and evaluated on the independent synthetic evaluation cohort, not on the "
            "operational synthetic assets and not on real utility data. Perfect or near-perfect "
            "metrics reflect deliberately separable synthetic outcomes."
        ),
        "artifact_persistence": (
            "The artifact is bind-mounted from ./ml/artifacts into the API container, so it "
            "survives API container restarts. The API loads it at request time and never retrains "
            "automatically."
        ),
    }


def _comparison() -> dict[str, Any] | None:
    path = EVALUATION_DIR / "model_comparison.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=1)
def predictive_overview() -> dict[str, Any]:
    """Return every model artifact plus comparison metadata (when available)."""
    models = [model_summary(name) for name in MODEL_NAMES]
    available = [model for model in models if model["available"]]
    preferred = next((model for model in available if model["model_name"] == DEFAULT_MODEL_NAME), None)
    if preferred is None and available:
        preferred = available[0]
    comparison = _comparison()
    return {
        "available": preferred is not None,
        "preferred_model": preferred,
        "models": models,
        "comparison": comparison,
        "comparison_available": comparison is not None,
        "message": None
        if preferred
        else "No trained model artifact found. Run: python -m data_engineering.cli train --model logistic_regression",
        "evaluation_dataset": "Independent synthetic evaluation cohort (not production data)",
        "synthetic_warning": (
            "All metrics are synthetic demonstration results. Do not present them as real-world "
            "utility performance or as evidence of production readiness."
        ),
    }


__all__ = ["METRIC_EXPLANATIONS", "model_summary", "predictive_overview"]
