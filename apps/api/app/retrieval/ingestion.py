"""Knowledge ingestion pipeline: chunk, embed, and persist a document into the
retrieval corpus (ARCHITECTURE.md sections 7-8). Explicit and audited --
agents only ever read this corpus through app.retrieval.search, never write
to it directly (AGENTS.md)."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from llama_index.core.node_parser import SentenceSplitter

from app.db.repositories import KnowledgeChunkRepository, KnowledgeDocumentRepository
from app.models.knowledge import IngestionStatus, KnowledgeChunk, KnowledgeDocument
from app.retrieval.embeddings import EmbeddingProvider


class KnowledgeIngestionService:
    def __init__(
        self,
        *,
        embeddings: EmbeddingProvider,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        self._embeddings = embeddings
        self._splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def ingest(
        self,
        *,
        document_repository: KnowledgeDocumentRepository,
        chunk_repository: KnowledgeChunkRepository,
        workspace_id: UUID,
        source_uri: str,
        text: str,
        source_metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        document = document_repository.add(
            KnowledgeDocument(
                workspace_id=workspace_id,
                source_uri=source_uri,
                source_metadata=source_metadata or {},
                ingestion_status=IngestionStatus.INGESTING,
                checksum=checksum,
            )
        )

        chunks = self._splitter.split_text(text)
        if not chunks:
            document.ingestion_status = IngestionStatus.FAILED
            return document

        vectors = self._embeddings.embed(chunks)
        for index, (chunk_text, vector) in enumerate(zip(chunks, vectors, strict=True)):
            chunk_repository.add(
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    chunk_text=chunk_text,
                    embedding=vector,
                )
            )
        document.ingestion_status = IngestionStatus.READY
        return document
