"""Local Hugging Face open-weight model provider (ARCHITECTURE.md section 2).

Targets a self-hosted, OpenAI-chat-compatible local server (e.g. Text
Generation Inference, vLLM, or a llama.cpp server) rather than any paid
hosted API — AGENTS.md requires local/open-weight models only. The schema is
both requested via ``response_format`` and restated in the system prompt,
since not every local server enforces the JSON schema strictly server-side;
either way the result is re-validated through Pydantic before use.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputValidationError, LLMProvider

logger = logging.getLogger(__name__)


class HuggingFaceProvider(LLMProvider):
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
        schema_instruction = (
            f"{system}\n\nRespond with only JSON matching this schema:\n"
            f"{response_model.model_json_schema()}"
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": schema_instruction},
            {"role": "user", "content": prompt},
        ]
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.post(
                    "/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "stream": False,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "huggingface_completion_transport_failed attempt=%s error=%s", attempt, exc
                )
                continue

            try:
                return response_model.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "huggingface_completion_validation_failed attempt=%s error=%s", attempt, exc
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
            f"Hugging Face endpoint did not produce valid {response_model.__name__} output "
            f"after {max_retries + 1} attempt(s)"
        ) from last_error
