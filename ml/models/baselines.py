"""Baseline classification models for GridOps Intelligence (Milestone 3).

Logistic regression is implemented in pure Python.  Random Forest and
HistGradientBoosting are implemented with scikit-learn, which is now an
explicit dependency of the project.
"""

from __future__ import annotations

import math
from typing import Any

from ml.features.asset import boolean_feature_names, categorical_feature_names, numeric_feature_names
from ml.models.pipeline import Preprocessor, train_logistic_regression, predict_logistic_probability


BASELINE_NAMES: tuple[str, ...] = ("logistic_regression", "random_forest", "hist_gradient_boosting")


class TrainedBaseline:
    """A trained baseline with its fitted preprocessing/model state and metrics."""

    def __init__(
        self,
        *,
        model_name: str,
        weights: list[float] | None = None,
        bias: float = 0.0,
        feature_names: list[str] | None = None,
        preprocessor: Preprocessor | None = None,
        sklearn_pipeline: Any = None,
        numeric_names: list[str] | None = None,
        categorical_names: list[str] | None = None,
        positive_count: int = 0,
        negative_count: int = 0,
        metrics: dict[str, float] | None = None,
        test_metrics: dict[str, float] | None = None,
        train_asset_ids: list[str] | None = None,
        validation_asset_ids: list[str] | None = None,
        test_asset_ids: list[str] | None = None,
        threshold: float = 0.5,
        seed: int = 0,
    ) -> None:
        self.model_name = model_name
        self.weights = list(weights or [])
        self.bias = float(bias)
        self.feature_names = list(feature_names or [])
        self.preprocessor = preprocessor
        self.sklearn_pipeline = sklearn_pipeline
        self.numeric_names = list(numeric_names) if numeric_names else (list(numeric_feature_names()) + list(boolean_feature_names()))
        self.categorical_names = list(categorical_names) if categorical_names else list(categorical_feature_names())
        self.positive_count = int(positive_count)
        self.negative_count = int(negative_count)
        self.metrics = dict(metrics or {})
        self.test_metrics = dict(test_metrics or {})
        self.train_asset_ids = list(train_asset_ids or [])
        self.validation_asset_ids = list(validation_asset_ids or [])
        self.test_asset_ids = list(test_asset_ids or [])
        self.threshold = float(threshold)
        self.seed = int(seed)


def build_baseline(model_name: str) -> TrainedBaseline:
    """Return an unfitted baseline handle."""
    if model_name not in BASELINE_NAMES:
        raise ValueError(f"unknown baseline model: {model_name}")
    return TrainedBaseline(model_name=model_name)


def train_logistic_regression_baseline(
    preprocessor: Preprocessor,
    X_train: list[list[float]],
    y_train: list[int],
) -> tuple[list[float], float]:
    """Fit the pure-Python logistic regression baseline."""
    return train_logistic_regression(X_train, y_train)


def predict_baseline_probability(trained: TrainedBaseline, X: list[list[float]]) -> list[float]:
    """Predict failure probabilities from a trained baseline."""
    if trained.sklearn_pipeline is not None:
        import numpy as np

        X_array = _sklearn_matrix(X, trained.numeric_names, trained.categorical_names)
        return [float(value) for value in trained.sklearn_pipeline.predict_proba(X_array)[:, 1]]
    vector = trained.preprocessor.transform(X) if trained.preprocessor is not None else X
    return predict_logistic_probability(trained.weights, trained.bias, vector)


def _sklearn_matrix(rows: list[dict[str, object]], numeric_names: list[str], categorical_names: list[str]):
    import numpy as np

    all_names = list(numeric_names) + list(categorical_names)
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
    array = np.array(matrix, dtype=object)
    for j, name in enumerate(all_names):
        if name in set(numeric_names):
            array[:, j] = np.array([float(row.get(name)) if row.get(name) is not None else float("nan") for row in rows], dtype=float)
    return array


def train_sklearn_baseline(
    model_name: str,
    rows: list[dict[str, object]],
    y: list[int],
    *,
    seed: int,
) -> TrainedBaseline:
    """Train a scikit-learn baseline (Random Forest or HistGradientBoosting)."""
    if model_name not in ("random_forest", "hist_gradient_boosting"):
        raise ValueError(f"not a scikit-learn baseline: {model_name}")
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    numeric_names = list(numeric_feature_names()) + list(boolean_feature_names())
    categorical_names = list(categorical_feature_names())
    numeric_indices = list(range(len(numeric_names)))
    categorical_indices = list(range(len(numeric_names), len(numeric_names) + len(categorical_names)))

    numeric_transformer = Pipeline(
        [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    )
    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    preprocess = ColumnTransformer(
        [("numeric", numeric_transformer, numeric_indices), ("categorical", categorical_transformer, categorical_indices)],
        remainder="drop",
    )
    if model_name == "random_forest":
        estimator = RandomForestClassifier(n_estimators=200, min_samples_leaf=5, random_state=seed, n_jobs=-1)
    else:
        estimator = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, random_state=seed)
    pipeline = Pipeline([("preprocess", preprocess), ("model", estimator)])

    X = _sklearn_matrix(rows, numeric_names, categorical_names)
    pipeline.fit(X, y)
    probabilities = pipeline.predict_proba(X)[:, 1]

    return TrainedBaseline(
        model_name=model_name,
        sklearn_pipeline=pipeline,
        feature_names=list(numeric_names) + list(categorical_names),
        numeric_names=numeric_names,
        categorical_names=categorical_names,
        positive_count=int(sum(y)),
        negative_count=int(len(y) - sum(y)),
        seed=seed,
    )


__all__ = [
    "BASELINE_NAMES",
    "TrainedBaseline",
    "build_baseline",
    "predict_baseline_probability",
    "train_logistic_regression_baseline",
    "train_sklearn_baseline",
]
