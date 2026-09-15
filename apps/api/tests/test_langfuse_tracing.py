"""LangfuseTracingProvider tests, using a mocked Langfuse client -- no live
Langfuse server required (AGENTS.md). Validates run_id/task_id correlation,
that the wrapped provider's result still passes through unchanged, and that
a failure is recorded as an ERROR-level generation before propagating."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.llm.base import LLMOutputValidationError
from app.llm.fake import FakeLLMProvider
from app.llm.tracing import LangfuseTracingProvider


class _Answer(BaseModel):
    value: int


def test_complete_wraps_call_in_a_trace_and_generation_correlated_by_ids() -> None:
    run_id, task_id = uuid4(), uuid4()
    client = MagicMock()
    trace = MagicMock()
    generation = MagicMock()
    client.trace.return_value = trace
    trace.generation.return_value = generation

    inner = FakeLLMProvider(responses=[_Answer(value=42)])
    provider = LangfuseTracingProvider(inner, client)

    result = provider.complete(
        system="sys", prompt="prompt", response_model=_Answer, run_id=run_id, task_id=task_id
    )

    assert result == _Answer(value=42)
    client.trace.assert_called_once()
    assert client.trace.call_args.kwargs["id"] == str(run_id)
    trace.generation.assert_called_once()
    assert trace.generation.call_args.kwargs["metadata"]["task_id"] == str(task_id)
    generation.end.assert_called_once_with(output={"value": 42})

    # The wrapped provider still actually ran, with the same correlation ids.
    assert inner.calls[0]["run_id"] == run_id
    assert inner.calls[0]["task_id"] == task_id


def test_complete_records_error_generation_and_still_raises() -> None:
    client = MagicMock()
    trace = MagicMock()
    generation = MagicMock()
    client.trace.return_value = trace
    trace.generation.return_value = generation

    inner = FakeLLMProvider(responses=[])  # no scripted response -> raises
    provider = LangfuseTracingProvider(inner, client)

    with pytest.raises(LLMOutputValidationError):
        provider.complete(system="sys", prompt="prompt", response_model=_Answer)

    generation.end.assert_called_once()
    assert generation.end.call_args.kwargs["level"] == "ERROR"
