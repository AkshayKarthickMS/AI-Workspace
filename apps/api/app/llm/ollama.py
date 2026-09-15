"""Ollama-backed LLM provider (ARCHITECTURE.md section 2 - local, free,
self-hostable). Uses Ollama's ``format`` parameter (a JSON schema) so the
model is constrained to the requested shape server-side, then re-validates
the result through Pydantic since model output is still untrusted input."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputValidationError, LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model = model
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def complete[T: BaseModel](
        self,
        *,
        system: str,
        prompt: str,
        response_model: type[T],
        max_retries: int = 1,
        run_id: UUID | None = None,
        task_id: UUID | None = None,
    ) -> T:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.post(
                    "/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "format": response_model.model_json_schema(),
                        "stream": False,
                    },
                )
                response.raise_for_status()
                content = response.json()["message"]["content"]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "ollama_completion_transport_failed attempt=%s error=%s", attempt, exc
                )
                continue

            try:
                return response_model.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "ollama_completion_validation_failed attempt=%s error=%s", attempt, exc
                )
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"That did not match the required JSON schema ({exc}). "
                            "Reply again with only valid JSON matching the schema."
                        ),
                    }
                )
        raise LLMOutputValidationError(
            f"Ollama did not produce valid {response_model.__name__} output after "
            f"{max_retries + 1} attempt(s)"
        ) from last_error
