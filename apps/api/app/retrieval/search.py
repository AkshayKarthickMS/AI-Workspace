"""Hybrid (vector + keyword) retrieval over the knowledge base (ARCHITECTURE.md
section 7). Vector ranking uses pgvector's cosine-distance operator on
PostgreSQL to narrow candidates in the database; the final score is always
computed in Python so this works identically (if less scalably) against any
SQLAlchemy-supported dialect, including SQLite in tests — pgvector is the
Day-1 default precisely so this doesn't need to scale that way in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.retrieval.embeddings import EmbeddingProvider, cosine_similarity

_KEYWORD_MATCH_BOOST = 0.05


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    text: str
    score: float
    source_uri: str


class HybridSearchService:
    def __init__(self, *, session: Session, embeddings: EmbeddingProvider) -> None:
        self.session = session
        self._embeddings = embeddings

    def search(self, *, workspace_id: UUID, query: str, limit: int = 5) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        query_vector = self._embeddings.embed([query])[0]
        keyword_terms = {term.lower() for term in query.split() if len(term) > 2}

        statement = (
            select(KnowledgeChunk, KnowledgeDocument.source_uri)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(KnowledgeDocument.workspace_id == workspace_id)
        )
        bind = self.session.get_bind()
        if bind.dialect.name == "postgresql":
            statement = statement.order_by(
                KnowledgeChunk.embedding.cosine_distance(query_vector)
            ).limit(limit * 3)
        rows = self.session.execute(statement).all()

        scored: list[RetrievedChunk] = []
        for chunk, source_uri in rows:
            score = cosine_similarity(query_vector, list(chunk.embedding))
            if keyword_terms and keyword_terms.intersection(chunk.chunk_text.lower().split()):
                score += _KEYWORD_MATCH_BOOST
            scored.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    text=chunk.chunk_text,
                    score=score,
                    source_uri=source_uri,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]
