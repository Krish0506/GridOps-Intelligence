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

    def ask(self, question: str, *, asset_id: str | None = None, top_k: int = 5, category: str | None = None, equipment: str | None = None):
        equipment = equipment or (equipment_filter_for_asset(asset_id) if asset_id else None)
        retrieved = self.search(question, top_k=top_k, category=category, equipment=equipment)
        citations = citations_from_retrieval(retrieved)
        citations = validate_citations(citations, retrieved)
        prompt = build_prompt(question, retrieved)
        answer = self.generator.generate(prompt)
        # A retrievable chunk is not automatically sufficient evidence.  Require
        # either a meaningful keyword match or a strong combined score.
        evidence_sufficient = any(
            float(item.get("keyword_score") or 0.0) >= 0.2
            or float(item.get("combined_score") or 0.0) >= 0.45
            for item in retrieved
        )
        if evidence_sufficient:
            top_score = max(float(item.get("combined_score") or 0.0) for item in retrieved)
            confidence = "high" if top_score >= 0.35 else "medium"
        else:
            confidence = "low"
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
            "confidence": confidence,
            "provider": getattr(self.generator, "model_name", "unknown"),
        }

    def ingest(self, source_dir, provider=None, *, force: bool = False):
        return ingest_directory(
            source_dir, self.repository, provider or self.provider, force=force
        )


__all__ = ["EvidenceService"]
