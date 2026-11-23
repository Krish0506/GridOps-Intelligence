"""Local model artifact and metadata persistence (Milestone 3, stdlib pickle)."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from ml.models.baselines import TrainedBaseline


def save_model(trained: TrainedBaseline, directory: Path) -> Path:
    """Persist a trained model pipeline plus its metadata JSON."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    artifact_path = directory / f"{trained.model_name}.pkl"
    with artifact_path.open("wb") as handle:
        pickle.dump(trained, handle)
    metadata = {
        "model_name": trained.model_name,
        "feature_names": trained.feature_names,
        "metrics": trained.metrics,
        "positive_count": trained.positive_count,
        "negative_count": trained.negative_count,
    }
    (directory / f"{trained.model_name}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return artifact_path


def load_model(path: Path) -> TrainedBaseline:
    """Load a persisted trained baseline from disk."""
    with Path(path).open("rb") as handle:
        return pickle.load(handle)


__all__ = ["load_model", "save_model"]
