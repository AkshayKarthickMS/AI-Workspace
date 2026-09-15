"""Langfuse tracing wrapper around any LLMProvider (ARCHITECTURE.md section 11).

Every LLM call is traced -- correlated to run_id/task_id -- against a
self-hosted Langfuse instance only, never a third-party SaaS (AGENTS.md).
The wrapped ``client`` is duck-typed (``.trace()`` returning an object with
``.generation()``/``.end()``) so tests can inject a mock instead of talking
to a live server.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.llm.base import LLMProvider


class LangfuseTracingProvider(LLMProvider):
    def __init__(self, inner: LLMProvider, client: Any) -> None:
        self._inner = inner
        self._client = client

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
        # One trace per run_id groups every LLM call in a mission under a
        # single Langfuse trace; each call is a child generation.
        trace = self._client.trace(
            id=str(run_id) if run_id else None,
            name="aegisos.llm_call",
            metadata={"task_id": str(task_id) if task_id else None},
        )
        generation = trace.generation(
            name=response_model.__name__,
            model=getattr(self._inner, "model", "unknown"),
            input={"system": system, "prompt": prompt},
            metadata={"task_id": str(task_id) if task_id else None, "max_retries": max_retries},
        )
        try:
            result = self._inner.complete(
                system=system,
                prompt=prompt,
                response_model=response_model,
                max_retries=max_retries,
                run_id=run_id,
                task_id=task_id,
            )
        except Exception as exc:
            generation.end(output=None, level="ERROR", status_message=str(exc)[:500])
            raise
        generation.end(output=result.model_dump(mode="json"))
        return result
