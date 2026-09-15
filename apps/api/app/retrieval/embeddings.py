"""Embedding provider interface (ARCHITECTURE.md section 7 retrieval; also
reused by the QA agent for claim-vs-evidence groundedness scoring)."""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Calls Ollama's batched ``/api/embed`` endpoint (e.g. ``nomic-embed-text``,
    768 dimensions — must match ``app.models.knowledge.EMBEDDING_DIMENSIONS``)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.post("/api/embed", json={"model": self.model, "input": texts})
        response.raise_for_status()
        embeddings = response.json()["embeddings"]
        return [[float(value) for value in vector] for vector in embeddings]


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Calls the free-tier Hugging Face Inference API's feature-extraction
    endpoint for the public demo deployment only (AGENTS.md documents this
    exception; local development and tests use ``OllamaEmbeddingProvider``/
    ``FakeEmbeddingProvider``). Some models return one pooled vector per
    input (2D response); others return per-token vectors (3D) that need
    mean-pooling client-side -- handled below since the Inference API's
    pooling behavior isn't consistent across all sentence-transformers
    models. Default model (``sentence-transformers/all-mpnet-base-v2``)
    produces 768 dimensions, matching ``app.models.knowledge.EMBEDDING_DIMENSIONS``.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://api-inference.huggingface.co/models",
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model = model
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.post(
            f"/{self.model}",
            json={"inputs": texts, "options": {"wait_for_model": True}},
        )
        response.raise_for_status()
        payload = response.json()
        return [self._as_vector(item) for item in payload]

    @staticmethod
    def _as_vector(item: Any) -> list[float]:
        # 2D response: item is already a flat vector (one pooled embedding).
        if item and isinstance(item[0], (int, float)):
            return [float(value) for value in item]
        # 3D response: item is a list of per-token vectors -- mean-pool them.
        token_vectors = [[float(value) for value in token] for token in item]
        dimensions = len(token_vectors[0])
        pooled = [0.0] * dimensions
        for token_vector in token_vectors:
            for index, value in enumerate(token_vector):
                pooled[index] += value
        count = len(token_vectors)
        return [value / count for value in pooled]


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashing-trick bag-of-words 'embedding' for tests. Texts
    that share more words score a higher cosine similarity than unrelated
    ones — real enough to test ranking/groundedness logic without a live model.
    """

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Constructs the configured ``EmbeddingProvider`` from ``Settings``
    (mirrors ``app.llm.factory.build_llm_provider``). Kept here rather than
    in ``llm/factory.py`` since embeddings are a retrieval concern, reused
    by the QA agent for groundedness scoring."""

    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url, model=settings.embedding_model_name
        )
    if settings.embedding_provider == "huggingface":
        return HuggingFaceEmbeddingProvider(
            model=settings.embedding_model_name, api_key=settings.embedding_api_key
        )
    raise ValueError(f"Unsupported AEGIS_EMBEDDING_PROVIDER: {settings.embedding_provider!r}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
