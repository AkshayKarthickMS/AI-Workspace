"""Knowledge base tables: ingested documents and their pgvector-embedded chunks
(ARCHITECTURE.md §7, §8). Ingestion itself is explicit and audited — agents
read this table via app.retrieval, never write to it directly (AGENTS.md)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    JsonObject,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column_type,
    json_column_type,
)

# Matches the default local embedding model (Ollama `nomic-embed-text`, 768
# dimensions). Changing embedding models means a migration that resizes this
# column and re-embeds existing chunks — it is not a runtime setting.
EMBEDDING_DIMENSIONS = 768


class IngestionStatus(StrEnum):
    PENDING = "pending"
    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    source_uri: Mapped[str] = mapped_column(String(500))
    source_metadata: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        enum_column_type(IngestionStatus, name="ingestion_status"), default=IngestionStatus.PENDING
    )
    checksum: Mapped[str] = mapped_column(String(128))


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_index"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    # Non-sensitive filter metadata only (ARCHITECTURE.md §8) - never raw
    # source content beyond chunk_text itself.
    chunk_metadata: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
