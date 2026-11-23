"""High-level Evidence Intelligence service."""

from __future__ import annotations

from rag.asset_integration import equipment_filter_for_asset
from rag.citations import citations_from_retrieval, validate_citations
from rag.generation import build_prompt, MockGenerationProvider
from rag.ingestion import ingest_directory
from rag.retrieval import rerank, search


class EvidenceService:
    """Orchestrate retrieval, reranking, and grounded generation."""

    def __init__(self, repository, provider, generator=None) -> None:
        self.repository = repository
        self.provider = provider
        self.generator = generator or MockGenerationProvider()

    def search(self, query: str, *, top_k: int = 5, category: str | None = None, equipment: str | None = None):
        results = search(self.repository, query, self.provider, top_k=top_k, category=category, equipment=equipment)
        return rerank(results)

    def ask(self, question: str, *, asset_id: str | None = None, top_k: int = 5):
        equipment = equipment_filter_for_asset(asset_id) if asset_id else None
        retrieved = self.search(question, top_k=top_k, equipment=equipment)
        citations = citations_from_retrieval(retrieved)
        citations = validate_citations(citations, retrieved)
        prompt = build_prompt(question, retrieved)
        answer = self.generator.generate(prompt)
        evidence_sufficient = len(retrieved) > 0
        return {
            "question": question,
            "asset_id": asset_id,
            "answer": answer if evidence_sufficient else "Insufficient evidence to answer the question.",
            "citations": citations,
            "key_facts": [item.get("text") for item in retrieved],
            "limitations": [
                "Synthetic demonstration documents; not official engineering standards.",
                "Anomaly scores and risk outputs are not calibrated failure probabilities.",
            ],
            "evidence_sufficient": evidence_sufficient,
            "confidence": "high" if evidence_sufficient and len(retrieved) >= 3 else "low",
            "provider": getattr(self.generator, "model_name", "unknown"),
        }

    def ingest(self, source_dir, provider=None):
        return ingest_directory(source_dir, self.repository, provider or self.provider)


__all__ = ["EvidenceService"]
