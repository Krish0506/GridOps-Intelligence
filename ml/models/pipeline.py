"""Pure-Python preprocessing and baseline logistic regression (Milestone 3).

The project venv intentionally does not add third-party numerical dependencies,
so the reusable preprocessing and baseline modelling logic is implemented with
standard-library Python only (median imputation, standardization, one-hot
encoding, and a deterministic L2-regularized logistic regression via gradient
descent).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ml.features.asset import boolean_feature_names, categorical_feature_names, numeric_feature_names


@dataclass
class Preprocessor:
    """Fitted preprocessing state over numeric and categorical model features."""

    numeric_names: list[str]
    categorical_names: list[str]
    numeric_medians: dict[str, float] = field(default_factory=dict)
    numeric_means: dict[str, float] = field(default_factory=dict)
    numeric_stds: dict[str, float] = field(default_factory=dict)
    categories: dict[str, list[str]] = field(default_factory=dict)

    def fit(self, rows: list[dict[str, object]]) -> None:
        values_by_name: dict[str, list[float]] = {name: [] for name in self.numeric_names}
        for row in rows:
            for name in self.numeric_names:
                value = row.get(name)
                values_by_name[name].append(float(value) if value is not None else float("nan"))
        for name, values in values_by_name.items():
            valid = [value for value in values if value == value]
            median = sorted(valid)[len(valid) // 2] if valid else 0.0
            mean = sum(valid) / len(valid) if valid else median
            variance = sum((value - mean) ** 2 for value in valid) / len(valid) if valid else 0.0
            std = math.sqrt(variance) if variance > 0 else 1e-9
            self.numeric_medians[name] = median
            self.numeric_means[name] = mean
            self.numeric_stds[name] = std
        for name in self.categorical_names:
            seen: list[str] = []
            for row in rows:
                value = row.get(name)
                text = str(value) if value is not None else "unknown"
                if text not in seen:
                    seen.append(text)
            self.categories[name] = sorted(seen)

    def _dense(self, row: dict[str, object]) -> list[float]:
        vector: list[float] = []
        for name in self.numeric_names:
            value = row.get(name)
            number = float(value) if value is not None else float("nan")
            imputed = self.numeric_medians.get(name, 0.0) if number != number else number
            mean = self.numeric_means.get(name, 0.0)
            std = self.numeric_stds.get(name, 1e-9)
            standardized = (imputed - mean) / std if std > 0 else 0.0
            vector.append(standardized)
        for name in self.categorical_names:
            categories = self.categories.get(name, [])
            value = str(row.get(name) if row.get(name) is not None else "unknown")
            vector.extend(1.0 if value == category else 0.0 for category in categories)
        return vector

    def transform(self, rows: list[dict[str, object]]) -> list[list[float]]:
        return [self._dense(row) for row in rows]


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def train_logistic_regression(
    X: list[list[float]],
    y: list[int],
    *,
    l2: float = 1e-3,
    learning_rate: float = 0.05,
    iterations: int = 400,
    tol: float = 1e-8,
) -> tuple[list[float], float]:
    """Fit an L2-regularized logistic regression by deterministic gradient descent."""
    n = len(X)
    d = len(X[0]) if X else 0
    weights = [0.0] * d
    bias = 0.0

    def loss() -> float:
        total = 0.0
        for index in range(n):
            z = bias + sum(weights[j] * X[index][j] for j in range(d))
            probability = _sigmoid(z)
            probability = min(max(probability, 1e-12), 1.0 - 1e-12)
            total += -(y[index] * math.log(probability) + (1 - y[index]) * math.log(1 - probability))
        return total / n + (l2 / 2.0) * sum(weight * weight for weight in weights)

    current_loss = loss()
    for _ in range(iterations):
        gradient_weights = [0.0] * d
        gradient_bias = 0.0
        for index in range(n):
            z = bias + sum(weights[j] * X[index][j] for j in range(d))
            error = _sigmoid(z) - y[index]
            gradient_bias += error
            for j in range(d):
                gradient_weights[j] += error * X[index][j]
        gradient_bias /= n
        gradient_weights = [
            (gradient_weights[j] / n) + (l2 * weights[j]) for j in range(d)
        ]
        bias -= learning_rate * gradient_bias
        weights = [weights[j] - learning_rate * gradient_weights[j] for j in range(d)]
        updated_loss = loss()
        if abs(updated_loss - current_loss) < tol:
            break
        current_loss = updated_loss
    return weights, bias


def predict_logistic_probability(weights: list[float], bias: float, X: list[list[float]]) -> list[float]:
    """Predict class probabilities for dense feature rows."""
    return [
        _sigmoid(bias + sum(weights[j] * row[j] for j in range(len(weights)))) for row in X
    ]


__all__ = ["Preprocessor", "predict_logistic_probability", "train_logistic_regression"]
