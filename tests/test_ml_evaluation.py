"""Tests for evaluation metrics (Milestone 3)."""

from __future__ import annotations

from ml.evaluation.metrics import classification_metrics


def test_classification_metrics_perfect_classifier() -> None:
    y_true = [0, 0, 1, 1]
    y_proba = [0.0, 0.1, 0.9, 1.0]
    metrics = classification_metrics(y_true, y_proba)
    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["confusion_matrix"]["true_positive"] == 2
    assert metrics["confusion_matrix"]["true_negative"] == 2
    assert metrics["prevalence"] == 0.5
    assert 0.0 <= metrics["brier"] <= 1.0


def test_classification_metrics_imperfect_classifier() -> None:
    y_true = [0, 0, 1, 1]
    y_proba = [0.8, 0.2, 0.3, 0.7]
    metrics = classification_metrics(y_true, y_proba)
    assert metrics["accuracy"] < 1.0
    assert metrics["confusion_matrix"]["false_positive"] >= 1
    assert metrics["confusion_matrix"]["false_negative"] >= 1
