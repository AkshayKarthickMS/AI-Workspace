from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AEGIS_", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    app_name: str = "AegisOS API"
    app_version: str = "0.1.0"
    database_url: str = (
        "postgresql+psycopg://aegisos:change-me-for-local-development@localhost:5432/aegisos"
    )

    # Local/open-weight model provider selection (AGENTS.md - never a paid
    # hosted model API). "ollama" or "huggingface".
    model_provider: str = "ollama"
    model_name: str = "qwen2.5:7b-instruct"
    embedding_model_name: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    # Local OpenAI-chat-compatible endpoint (e.g. TGI, vLLM, llama.cpp server).
    huggingface_endpoint_url: str = "http://localhost:8080"

    # Sandboxed code execution limits (Analyst agent).
    sandbox_timeout_seconds: int = 30
    sandbox_memory_limit_mb: int = 512
    sandbox_cpu_limit: float = 1.0

    # Ephemeral event bus (SSE fan-out / cross-agent notification) - never a
    # system of record, see AGENTS.md.
    redis_url: str = "redis://localhost:6379/0"

    # Relative to the process's working directory. The default matches
    # running `uvicorn` from apps/api (the documented local-dev command);
    # docker-compose.yml overrides this to "data" for the container, where
    # the Dockerfile copies data/ to /app/data.
    data_root: str = "../../data/demo"
    artifact_root: str = "../../data/artifacts"

    # Self-hosted Langfuse tracing. Tracing is disabled (no-op) whenever
    # either key is blank, which is the default until a project is created in
    # the local Langfuse instance (see infra "observability" Compose profile).
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
