"""Grounded answer generation for GridOps Intelligence (Milestone 4)."""

from __future__ import annotations

import json
import urllib.request
from typing import Protocol


class GenerationProvider(Protocol):
    model_name: str

    def generate(self, prompt: str) -> str: ...


class MockGenerationProvider:
    """Deterministic mock generator for tests and offline use."""

    def __init__(self, model_name: str = "mock-generator") -> None:
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        # Extract the question line and evidence count for a deterministic answer.
        question = ""
        evidence_count = 0
        for line in prompt.splitlines():
            if line.startswith("Question:"):
                question = line[len("Question:") :].strip()
            if line.startswith("Evidence "):
                evidence_count += 1
        if evidence_count == 0:
            return "Insufficient evidence: no supporting documents were retrieved."
        return (
            f"Based on the retrieved evidence, the following considerations apply to: {question}. "
            "The cited documents provide relevant engineering guidance; consult the cited sources for details."
        )


class OllamaGenerationProvider:
    """Optional Ollama generation provider using the HTTP API."""

    def __init__(self, model_name: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str) -> str:
        payload = {"model": self.model_name, "prompt": prompt, "stream": False}
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body.get("response") or "")


def build_prompt(question: str, evidence: list[dict]) -> str:
    """Build a grounded prompt with explicit evidence and citation rules."""
    lines = [
        "You are an engineering assistant. Answer only from the supplied evidence.",
        "Cite every material factual claim using the provided evidence numbers.",
        "Do not invent technical thresholds, procedures, or citations.",
        "State clearly when evidence is insufficient.",
        "Do not claim that any asset will fail.",
        "",
        f"Question: {question}",
        "",
        "Evidence:",
    ]
    for index, item in enumerate(evidence, start=1):
        lines.append(f"Evidence {index}: {item.get('text')}")
    if not evidence:
        lines.append("No evidence retrieved.")
    return "\n".join(lines)


__all__ = ["GenerationProvider", "MockGenerationProvider", "OllamaGenerationProvider", "build_prompt"]
