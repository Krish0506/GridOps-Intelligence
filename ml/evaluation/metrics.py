"""Model evaluation metrics for GridOps Intelligence (Milestone 3, pure Python)."""

from __future__ import annotations

from collections.abc import Sequence


def _rank_based_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Compute ROC-AUC from pairwise concordance (pure Python)."""
    positives = sorted(
        (score, label) for score, label in zip(scores, labels) if label == 1
    )
    negatives = sorted(
        (score, label) for score, label in zip(scores, labels) if label == 0
    )
    if not positives or not negatives:
        return float("nan")
    concordant = 0
    ties = 0
    for positive_score, _positive_label in positives:
        for negative_score, _negative_label in negatives:
            if positive_score > negative_score:
                concordant += 1
            elif positive_score == negative_score:
                ties += 1
    total = len(positives) * len(negatives)
    if total == 0:
        return float("nan")
    return (concordant + 0.5 * ties) / total


def _average_precision(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Compute the area under the precision-recall curve (pure Python)."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    positives = [i for i, label in enumerate(labels) if label == 1]
    total_positives = len(positives)
    if total_positives == 0:
        return float("nan")
    tp = 0
    fp = 0
    area = 0.0
    last_recall = 0.0
    for index in order:
        if labels[index] == 1:
            tp += 1
        else:
            fp += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / total_positives
        area += precision * max(0.0, recall - last_recall)
        last_recall = recall
    return area


def classification_metrics(y_true: Sequence[int], y_proba: Sequence[float], *, threshold: float = 0.5) -> dict[str, float]:
    """Compute supervised binary-model metrics in pure Python."""
    count = len(y_true)
    predictions = [1 if probability >= threshold else 0 for probability in y_proba]
    true_positive = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 1 and predicted == 1)
    false_positive = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 0 and predicted == 1)
    false_negative = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 1 and predicted == 0)
    true_negative = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 0 and predicted == 0)

    accuracy = (true_positive + true_negative) / count if count else 0.0
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    brier = sum((probability - actual) ** 2 for probability, actual in zip(y_proba, y_true)) / count if count else 0.0
    roc_auc = _rank_based_auc(list(y_proba), list(y_true))
    average_precision = _average_precision(list(y_proba), list(y_true))
    prevalence = sum(y_true) / count if count else 0.0

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "brier": float(brier),
        "roc_auc": float(roc_auc),
        "average_precision": float(average_precision),
        "confusion_matrix": {
            "true_negative": int(true_negative),
            "false_positive": int(false_positive),
            "true_positive": int(true_positive),
            "false_negative": int(false_negative),
        },
        "prevalence": float(prevalence),
    }


def tune_threshold(y_true: Sequence[int], y_proba: Sequence[float]) -> float:
    """Select a classification threshold by maximizing F1 on the supplied data."""
    if not y_true or not y_proba:
        return 0.5
    candidates = sorted(set(float(value) for value in y_proba) | {0.5})
    best_threshold = 0.5
    best_f1 = -1.0
    for threshold in candidates:
        predictions = [1 if probability >= threshold else 0 for probability in y_proba]
        true_positive = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 1 and predicted == 1)
        false_positive = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 0 and predicted == 1)
        false_negative = sum(1 for actual, predicted in zip(y_true, predictions) if actual == 1 and predicted == 0)
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0.0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
    return float(best_threshold)


__all__ = ["_average_precision", "_rank_based_auc", "classification_metrics", "tune_threshold"]
