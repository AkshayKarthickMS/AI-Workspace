"""Research tool: returns only approved evidence -- caller-supplied static
sources, plus (when configured) chunks retrieved from the ingested knowledge
base via hybrid search. Never synthesizes a source or fetches one live."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from app.retrieval.search import HybridSearchService
from app.schemas.agents import Evidence


class ControlledResearchTool:
    """Return only caller-supplied, approved evidence; never synthesize sources."""

    def __init__(
        self,
        sources: Iterable[Evidence] = (),
        *,
        retrieval: HybridSearchService | None = None,
        workspace_id: UUID | None = None,
    ) -> None:
        self._sources = list(sources)
        self._retrieval = retrieval
        self._workspace_id = workspace_id

    def search(self, query: str) -> list[Evidence]:
        if not query.strip():
            return []
        evidence = self._search_static(query)
        if self._retrieval is not None and self._workspace_id is not None:
            evidence = [*evidence, *self._search_retrieval(query)]
        return evidence

    def _search_static(self, query: str) -> list[Evidence]:
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        if not query_terms:
            return list(self._sources)
        return [
            evidence
            for evidence in self._sources
            if not evidence.excerpt
            or query_terms.intersection(set(evidence.excerpt.lower().split()))
        ]

    def _search_retrieval(self, query: str) -> list[Evidence]:
        assert self._retrieval is not None
        assert self._workspace_id is not None
        chunks = self._retrieval.search(workspace_id=self._workspace_id, query=query)
        return [
            Evidence(
                source=chunk.source_uri,
                source_type="document",
                locator=f"chunk:{chunk.chunk_id}",
                excerpt=chunk.text[:500],
                metadata={"score": round(chunk.score, 4)},
            )
            for chunk in chunks
        ]
