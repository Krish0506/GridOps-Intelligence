"""Tests for preprocessing and baseline models (Milestone 3)."""

from __future__ import annotations

from ml.models.pipeline import Preprocessor
from ml.models.baselines import BASELINE_NAMES, build_baseline, predict_baseline_probability
from ml.models.pipeline import Preprocessor, train_logistic_regression, predict_logistic_probability
from ml.models.pipeline import train_logistic_regression, predict_logistic_probability


def _rows() -> list[dict[str, object]]:
    return [
        {"numeric_a": 1.0, "numeric_b": 2.0, "category": "alpha"},
        {"numeric_a": 2.0, "numeric_b": 3.0, "category": "beta"},
        {"numeric_a": None, "numeric_b": 4.0, "category": "alpha"},
        {"numeric_a": 4.0, "numeric_b": None, "category": "gamma"},
    ]


def test_preprocessor_fits_and_transforms() -> None:
    preprocessor = Preprocessor(
        numeric_names=["numeric_a", "numeric_b"],
        categorical_names=["category"],
    )
    preprocessor.fit(_rows())
    vectors = preprocessor.transform(_rows())
    assert len(vectors) == 4
    assert all(len(vector) == 2 + 3 for vector in vectors)


def test_unavailable_baselines_raise_clearly() -> None:
    try:
        build_baseline("not_a_model")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown model should raise ValueError")


def test_logistic_regression_trains_and_predicts() -> None:
    X = [[0.0], [0.5], [1.0], [1.5]]
    y = [0, 0, 1, 1]
    weights, bias = train_logistic_regression(X, y)
    probabilities = predict_logistic_probability(weights, bias, X)
    assert len(probabilities) == 4
    assert all(0.0 <= probability <= 1.0 for probability in probabilities)
    assert probabilities[0] < probabilities[-1]


def test_base_names_contract() -> None:
    assert "logistic_regression" in BASELINE_NAMES
