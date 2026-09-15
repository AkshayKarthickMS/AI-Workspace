"""Unit tests for the Ollama/Hugging Face LLM providers, using httpx's mock
transport -- no live network call or model required (AGENTS.md)."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from app.llm.base import LLMOutputValidationError
from app.llm.huggingface import HuggingFaceProvider
from app.llm.ollama import OllamaProvider


class _Answer(BaseModel):
    value: int


def test_ollama_provider_returns_validated_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps({"value": 42})}})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ollama.test")
    provider = OllamaProvider(
        base_url="http://ollama.test", model="qwen2.5:7b-instruct", client=client
    )

    result = provider.complete(system="sys", prompt="prompt", response_model=_Answer)

    assert result == _Answer(value=42)


def test_ollama_provider_retries_on_invalid_json_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(200, json={"message": {"content": "not json"}})
        return httpx.Response(200, json={"message": {"content": json.dumps({"value": 7})}})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ollama.test")
    provider = OllamaProvider(base_url="http://ollama.test", model="m", client=client)

    result = provider.complete(system="sys", prompt="prompt", response_model=_Answer, max_retries=1)

    assert result == _Answer(value=7)
    assert attempts["count"] == 2


def test_ollama_provider_raises_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "still not json"}})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ollama.test")
    provider = OllamaProvider(base_url="http://ollama.test", model="m", client=client)

    with pytest.raises(LLMOutputValidationError):
        provider.complete(system="sys", prompt="prompt", response_model=_Answer, max_retries=1)


def test_huggingface_provider_returns_validated_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"value": 3})}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://hf.test")
    provider = HuggingFaceProvider(base_url="http://hf.test", model="m", client=client)

    result = provider.complete(system="sys", prompt="prompt", response_model=_Answer)

    assert result == _Answer(value=3)


def test_huggingface_provider_raises_on_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://hf.test")
    provider = HuggingFaceProvider(base_url="http://hf.test", model="m", client=client)

    with pytest.raises(LLMOutputValidationError):
        provider.complete(system="sys", prompt="prompt", response_model=_Answer, max_retries=0)
