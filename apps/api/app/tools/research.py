from collections.abc import Iterable

from app.schemas.agents import Evidence


class ControlledResearchTool:
    """Return only caller-supplied, approved evidence; never synthesize sources."""

    def __init__(self, sources: Iterable[Evidence] = ()) -> None:
        self._sources = list(sources)

    def search(self, query: str) -> list[Evidence]:
        if not query.strip():
            return []
        query_terms = {term.lower() for term in query.split() if len(term) > 2}
        if not query_terms:
            return list(self._sources)
        return [
            evidence
            for evidence in self._sources
            if not evidence.excerpt
            or query_terms.intersection(set(evidence.excerpt.lower().split()))
        ]
