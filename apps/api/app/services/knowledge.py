"""Knowledge ingestion use cases (ARCHITECTURE.md section 7, section 9).
Ingestion is explicit and audited -- this is the only path that writes to
the retrieval corpus (AGENTS.md); agents only ever read it."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import KnowledgeChunkRepository, KnowledgeDocumentRepository
from app.models.knowledge import KnowledgeDocument
from app.retrieval.embeddings import EmbeddingProvider, build_embedding_provider
from app.retrieval.ingestion import KnowledgeIngestionService


def ingest_document(
    session: Session,
    *,
    workspace_id: UUID,
    source_uri: str,
    text: str,
    source_metadata: dict[str, Any] | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> KnowledgeDocument:
    if embeddings is None:
        embeddings = build_embedding_provider(get_settings())
    ingestion = KnowledgeIngestionService(embeddings=embeddings)
    return ingestion.ingest(
        document_repository=KnowledgeDocumentRepository(session),
        chunk_repository=KnowledgeChunkRepository(session),
        workspace_id=workspace_id,
        source_uri=source_uri,
        text=text,
        source_metadata=source_metadata,
    )


def list_documents(
    session: Session, *, workspace_id: UUID, limit: int = 100, offset: int = 0
) -> list[KnowledgeDocument]:
    return KnowledgeDocumentRepository(session).list_for_workspace(
        workspace_id, limit=limit, offset=offset
    )
