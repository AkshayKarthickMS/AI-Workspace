"""Knowledge document and chunk repositories.

Vector similarity search belongs to ``app.retrieval`` (hybrid search over
these chunks), not here — this stays plain CRUD/listing, per ARCHITECTURE.md
section 7's split between persistence and retrieval.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument


class KnowledgeDocumentRepository(WorkspaceScopedRepository[KnowledgeDocument]):
    model = KnowledgeDocument

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[KnowledgeDocument]]:
        return select(KnowledgeDocument).where(KnowledgeDocument.workspace_id == workspace_id)


class KnowledgeChunkRepository(WorkspaceScopedRepository[KnowledgeChunk]):
    model = KnowledgeChunk

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[KnowledgeChunk]]:
        return (
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(KnowledgeDocument.workspace_id == workspace_id)
        )

    def list_for_document(self, workspace_id: UUID, document_id: UUID) -> list[KnowledgeChunk]:
        statement = (
            self._scoped_select(workspace_id)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index)
        )
        return list(self.session.execute(statement).scalars().all())
