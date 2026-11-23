"""Reusable training and inference workflows (Milestone 3, pure Python + scikit-learn)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from ml.data.cohort import ModelingDataset
from ml.evaluation.metrics import classification_metrics, tune_threshold
from ml.features.asset import boolean_feature_names, categorical_feature_names, numeric_feature_names
from ml.models.baselines import (
    TrainedBaseline,
    predict_baseline_probability,
    train_logistic_regression_baseline,
    train_sklearn_baseline,
)
from ml.models.pipeline import Preprocessor, predict_logistic_probability, train_logistic_regression

DEFAULT_TRAIN_FRACTION = 0.6
DEFAULT_VALIDATION_FRACTION = 0.2


def stratified_split(
    asset_ids: list[str],
    labels: list[int],
    *,
    seed: int,
    train_fraction: float = DEFAULT_TRAIN_FRACTION,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
) -> tuple[list[int], list[int], list[int]]:
    """Deterministic asset-level stratified split into train/validation/test."""
    rng = random.Random(seed)
    by_class: dict[int, list[int]] = {}
    for index, label in enumerate(labels):
        by_class.setdefault(int(label), []).append(index)

    train_indices: list[int] = []
    validation_indices: list[int] = []
    test_indices: list[int] = []
    for class_label, indices in by_class.items():
        shuffled = list(indices)
        rng.shuffle(shuffled)
        train_count = int(len(shuffled) * train_fraction)
        validation_count = int(len(shuffled) * validation_fraction)
        train_indices.extend(shuffled[:train_count])
        validation_indices.extend(shuffled[train_count : train_count + validation_count])
        test_indices.extend(shuffled[train_count + validation_count :])

    return sorted(train_indices), sorted(validation_indices), sorted(test_indices)


@dataclass
class TrainedBaselineWithMetrics(TrainedBaseline):
    """Trained baseline plus its validation/test metrics."""

    metrics: dict[str, float] | None = None
    test_metrics: dict[str, float] | None = None
    threshold: float = 0.5


def train_baseline(
    dataset: ModelingDataset,
    model_name: str,
    *,
    seed: int,
    train_fraction: float = DEFAULT_TRAIN_FRACTION,
    validation_fraction: float = DEFAULT_VALIDATION_FRACTION,
) -> TrainedBaseline:
    """Train a baseline model on a deterministic asset-level three-way split."""
    if model_name not in ("logistic_regression", "random_forest", "hist_gradient_boosting"):
        raise ValueError(f"unknown baseline model: {model_name}")

    train_indices, validation_indices, test_indices = stratified_split(
        dataset.asset_ids,
        dataset.labels,
        seed=seed,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )

    train_rows = [dataset.features[i] for i in train_indices]
    validation_rows = [dataset.features[i] for i in validation_indices]
    test_rows = [dataset.features[i] for i in test_indices]
    y_train = [dataset.labels[i] for i in train_indices]
    y_validation = [dataset.labels[i] for i in validation_indices]
    y_test = [dataset.labels[i] for i in test_indices]

    if model_name == "logistic_regression":
        preprocessor = Preprocessor(
            numeric_names=list(numeric_feature_names()) + list(boolean_feature_names()),
            categorical_names=list(categorical_feature_names()),
        )
        preprocessor.fit(train_rows)
        X_train = preprocessor.transform(train_rows)
        X_validation = preprocessor.transform(validation_rows)
        X_test = preprocessor.transform(test_rows)
        weights, bias = train_logistic_regression(X_train, y_train)
        trained = TrainedBaseline(
            model_name=model_name,
            weights=weights,
            bias=bias,
            feature_names=list(preprocessor.numeric_names)
            + [name for name in preprocessor.categorical_names for _ in preprocessor.categories.get(name, [])],
            preprocessor=preprocessor,
            positive_count=dataset.positive_count,
            negative_count=dataset.negative_count,
            seed=seed,
        )
        validation_probabilities = predict_logistic_probability(trained.weights, trained.bias, X_validation)
        test_probabilities = predict_logistic_probability(trained.weights, trained.bias, X_test)
    else:
        trained = train_sklearn_baseline(model_name, train_rows, y_train, seed=seed)
        validation_probabilities = predict_baseline_probability(trained, validation_rows)
        test_probabilities = predict_baseline_probability(trained, test_rows)

    threshold = tune_threshold(y_validation, validation_probabilities)
    validation_metrics = classification_metrics(y_validation, validation_probabilities, threshold=threshold)
    test_metrics = classification_metrics(y_test, test_probabilities, threshold=threshold)

    trained.metrics = validation_metrics
    trained.test_metrics = test_metrics
    trained.threshold = threshold
    trained.train_asset_ids = [dataset.asset_ids[i] for i in train_indices]
    trained.validation_asset_ids = [dataset.asset_ids[i] for i in validation_indices]
    trained.test_asset_ids = [dataset.asset_ids[i] for i in test_indices]
    return trained


def predict_positive_probability(trained: TrainedBaseline, snapshot: dict[str, object]) -> float:
    """Predict a failure probability for one snapshot using the trained baseline."""
    if trained.sklearn_pipeline is not None:
        import numpy as np

        X = _sklearn_matrix([snapshot], trained.numeric_names, trained.categorical_names)
        return float(trained.sklearn_pipeline.predict_proba(X)[:, 1][0])
    vector = trained.preprocessor.transform([snapshot])
    probabilities = predict_logistic_probability(trained.weights, trained.bias, vector)
    return float(probabilities[0])


def _sklearn_matrix(rows: list[dict[str, object]], numeric_names: list[str], categorical_names: list[str]):
    import numpy as np

    matrix = []
    for row in rows:
        record = []
        for name in numeric_names:
            value = row.get(name)
            record.append(float(value) if value is not None else float("nan"))
        for name in categorical_names:
            value = row.get(name)
            record.append(str(value) if value is not None else "unknown")
        matrix.append(record)
    return np.array(matrix, dtype=object)


__all__ = [
    "DEFAULT_TRAIN_FRACTION",
    "DEFAULT_VALIDATION_FRACTION",
    "TrainedBaseline",
    "predict_positive_probability",
    "stratified_split",
    "train_baseline",
]
