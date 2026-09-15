"""Provider-neutral LLM interface (ARCHITECTURE.md section 2, AGENTS.md).

Every call returns a validated Pydantic instance, never raw text: model
output is untrusted input until it passes ``response_model``'s validation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from pydantic import BaseModel


class LLMOutputValidationError(RuntimeError):
    """Raised when a provider could not produce output matching the requested
    schema within its retry budget."""


class LLMProvider(ABC):
    """A structured-output-only chat completion provider.

    Implementations must never execute or evaluate model output as code or
    instructions — the caller always receives a validated data object.
    """

    @abstractmethod
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
        """Return a ``response_model`` instance validated from the model's output.

        ``max_retries`` bounds *additional* attempts after a first failure
        (validation error or malformed JSON) — the total number of model
        calls is at most ``max_retries + 1``. Implementations should append a
        short error hint to the retry prompt so the model can self-correct.

        ``run_id``/``task_id`` are optional correlation identifiers for
        observability (ARCHITECTURE.md section 11) — implementations that
        don't trace may ignore them; ``LangfuseTracingProvider`` uses them to
        group every call in one run under a single trace.
        """
        raise NotImplementedError
