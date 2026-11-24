"""Runtime paths and model-artifact helpers shared by the API.

The API runs in two places during local development: on the Windows host via
``uvicorn`` and inside the Docker API container.  In both cases the project
root is the current working directory (``/app`` in Docker), and the artifact
directory is bind-mounted from the host.  Resolving paths from this module
prevents the API and the CLI from silently using different artifact locations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = PROJECT_ROOT / "ml" / "artifacts"
MODEL_DIR = ARTIFACT_ROOT / "models"
EXPLAINABILITY_DIR = ARTIFACT_ROOT / "explainability"
EVALUATION_DIR = ARTIFACT_ROOT / "evaluation"

MODEL_NAMES: tuple[str, ...] = ("logistic_regression", "random_forest", "hist_gradient_boosting")
DEFAULT_MODEL_NAME = "logistic_regression"

MODEL_LABELS = {
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "hist_gradient_boosting": "HistGradientBoosting",
}


def model_artifact_path(model_name: str = DEFAULT_MODEL_NAME) -> Path:
    """Return the persisted pickle path for ``model_name``."""
    return MODEL_DIR / f"{model_name}.pkl"


def model_metadata_path(model_name: str = DEFAULT_MODEL_NAME) -> Path:
    """Return the persisted metadata path for ``model_name``."""
    return MODEL_DIR / f"{model_name}.json"


def load_model_metadata(model_name: str) -> dict[str, Any] | None:
    """Load a model metadata JSON file, returning ``None`` when absent/corrupt."""
    path = model_metadata_path(model_name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def file_fingerprint(path: Path) -> str:
    """Return a short SHA-256 fingerprint for an artifact file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def artifact_version(model_name: str) -> str:
    """Return a stable human-readable artifact version (name@fingerprint)."""
    path = model_artifact_path(model_name)
    if not path.exists():
        return f"{model_name}@missing"
    return f"{model_name}@{file_fingerprint(path)}"


def artifact_mtime(path: Path) -> str | None:
    """Return an ISO-8601 UTC modification timestamp for an artifact."""
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def safe_artifact_reference(path: Path) -> str:
    """Return a project-relative artifact reference when possible."""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return path.name


__all__ = [
    "ARTIFACT_ROOT",
    "DEFAULT_MODEL_NAME",
    "EVALUATION_DIR",
    "EXPLAINABILITY_DIR",
    "MODEL_DIR",
    "MODEL_LABELS",
    "MODEL_NAMES",
    "PROJECT_ROOT",
    "artifact_mtime",
    "artifact_version",
    "file_fingerprint",
    "load_model_metadata",
    "model_artifact_path",
    "model_metadata_path",
    "safe_artifact_reference",
]
