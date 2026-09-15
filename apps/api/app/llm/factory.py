"""Constructs the configured ``LLMProvider`` from ``Settings`` (ARCHITECTURE.md
section 2). Production code should go through this rather than instantiating
a provider directly, so provider selection stays a config concern."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.huggingface import HuggingFaceProvider
from app.llm.ollama import OllamaProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.model_provider == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.model_name)
    if settings.model_provider == "huggingface":
        return HuggingFaceProvider(
            base_url=settings.huggingface_endpoint_url,
            model=settings.model_name,
            api_key=settings.huggingface_api_key,
        )
    raise ValueError(f"Unsupported AEGIS_MODEL_PROVIDER: {settings.model_provider!r}")


def build_traced_llm_provider(
    settings: Settings, provider: LLMProvider | None = None
) -> LLMProvider:
    """Wrap ``build_llm_provider`` (or a caller-supplied provider) with
    Langfuse tracing when both API keys are configured; otherwise return it
    unwrapped (ARCHITECTURE.md section 11 - tracing is additive, never a
    dependency the runtime requires to function)."""

    base_provider = provider or build_llm_provider(settings)
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return base_provider

    from langfuse import Langfuse

    from app.llm.tracing import LangfuseTracingProvider

    client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    return LangfuseTracingProvider(base_provider, client)
