"""Embedding providers for GridOps Intelligence (Milestone 4)."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbeddingProvider:
    """Deterministic hash-based embedding provider for tests and offline use."""

    def __init__(self, dimension: int = 64, model_name: str = "mock-embedding") -> None:
        self.dimension = dimension
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vector = []
            for i in range(self.dimension):
                byte = digest[i % len(digest)]
                vector.append((byte / 255.0) * 2.0 - 1.0)
            vectors.append(vector)
        return vectors


class OllamaEmbeddingProvider:
    """Optional Ollama embedding provider using the HTTP API."""

    def __init__(self, model_name: str = "bge-m3", base_url: str = "http://localhost:11434", dimension: int = 1024) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            payload = {"model": self.model_name, "prompt": text}
            request = urllib.request.Request(
                f"{self.base_url}/api/embeddings",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            vector = body.get("embedding")
            if not isinstance(vector, list):
                raise ValueError("Ollama response did not include an embedding")
            vectors.append([float(value) for value in vector])
        return vectors


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


__all__ = ["EmbeddingProvider", "MockEmbeddingProvider", "OllamaEmbeddingProvider", "cosine_similarity"]
