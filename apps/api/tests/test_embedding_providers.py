"""Unit tests for the embedding providers, using httpx's mock transport --
no live network call or model required (AGENTS.md)."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.retrieval.embeddings import (
    HuggingFaceEmbeddingProvider,
    OllamaEmbeddingProvider,
    build_embedding_provider,
)


def test_huggingface_embedding_provider_returns_pooled_vector_unchanged() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://hf.test")
    provider = HuggingFaceEmbeddingProvider(model="m", api_key="k", client=client)

    result = provider.embed(["a", "b"])

    assert result == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


def test_huggingface_embedding_provider_mean_pools_per_token_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 3D response: one input, two token vectors to mean-pool.
        return httpx.Response(200, json=[[[1.0, 3.0], [3.0, 5.0]]])

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://hf.test")
    provider = HuggingFaceEmbeddingProvider(model="m", api_key="k", client=client)

    result = provider.embed(["a"])

    assert result == [[2.0, 4.0]]


def test_huggingface_embedding_provider_empty_input_short_circuits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called for empty input")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://hf.test")
    provider = HuggingFaceEmbeddingProvider(model="m", api_key="k", client=client)

    assert provider.embed([]) == []


def test_huggingface_embedding_provider_sends_bearer_token() -> None:
    provider = HuggingFaceEmbeddingProvider(model="m", api_key="secret-token")

    assert provider._client.headers["Authorization"] == "Bearer secret-token"


def test_build_embedding_provider_selects_ollama_by_default() -> None:
    settings = Settings()

    provider = build_embedding_provider(settings)

    assert isinstance(provider, OllamaEmbeddingProvider)


def test_build_embedding_provider_selects_huggingface() -> None:
    settings = Settings(embedding_provider="huggingface", embedding_api_key="k")

    provider = build_embedding_provider(settings)

    assert isinstance(provider, HuggingFaceEmbeddingProvider)


def test_build_embedding_provider_rejects_unknown_provider() -> None:
    settings = Settings(embedding_provider="not-a-provider")

    with pytest.raises(ValueError, match="Unsupported AEGIS_EMBEDDING_PROVIDER"):
        build_embedding_provider(settings)
