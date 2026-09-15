"""Task input/result contracts for the Analyst agent's sandboxed code-execution
tool (ARCHITECTURE.md §7, §10, §12). The sandbox itself (network isolation,
resource limits, redaction) is Phase 3 tool-adapter work; this only fixes the
validated shape of its request/response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CodeExecutionInput(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    dataset_path: str | None = Field(default=None, max_length=500)


class CodeExecutionResult(BaseModel):
    exit_status: int
    stdout: str = Field(default="", max_length=20000)
    stderr: str = Field(default="", max_length=20000)
    duration_ms: int = Field(ge=0)
    timed_out: bool = False
