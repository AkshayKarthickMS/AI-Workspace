"""Deterministic fake LLM provider for tests (AGENTS.md: use fake LLMs/tools
in automated tests; no CI test may require a downloaded model)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.llm.base import LLMOutputValidationError, LLMProvider


class FakeLLMProvider(LLMProvider):
    """Returns pre-scripted responses in call order, or via a per-call factory.

    Construct with either ``responses`` (a fixed queue, consumed in order) or
    ``factory`` (called with the requested ``response_model``/``system``/
    ``prompt`` each time) — most tests only need one or the other. Every call
    is recorded on ``self.calls`` so a test can assert on what was asked.
    """

    def __init__(
        self,
        responses: list[BaseModel] | None = None,
        *,
        factory: Callable[[type[BaseModel], str, str], BaseModel] | None = None,
    ) -> None:
        self._responses = deque(responses or [])
        self._factory = factory
        self.calls: list[dict[str, Any]] = []

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
        self.calls.append(
            {
                "system": system,
                "prompt": prompt,
                "response_model": response_model,
                "run_id": run_id,
                "task_id": task_id,
            }
        )
        if self._factory is not None:
            result: BaseModel = self._factory(response_model, system, prompt)
        elif self._responses:
            result = self._responses.popleft()
        else:
            raise LLMOutputValidationError("FakeLLMProvider has no scripted response left")
        if not isinstance(result, response_model):
            raise LLMOutputValidationError(
                f"FakeLLMProvider was asked for {response_model.__name__} but had "
                f"{type(result).__name__} queued"
            )
        return result
