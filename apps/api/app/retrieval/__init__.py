"""Knowledge ingestion and hybrid vector/keyword retrieval (see ARCHITECTURE.md
section 7, section 8)."""

from app.retrieval.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OllamaEmbeddingProvider,
    cosine_similarity,
)
from app.retrieval.ingestion import KnowledgeIngestionService
from app.retrieval.search import HybridSearchService, RetrievedChunk

__all__ = [
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "HybridSearchService",
    "KnowledgeIngestionService",
    "OllamaEmbeddingProvider",
    "RetrievedChunk",
    "cosine_similarity",
]
