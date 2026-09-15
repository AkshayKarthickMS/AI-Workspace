"""Task input/result contracts for the Data agent's text-to-SQL tool
(ARCHITECTURE.md §7, §10). ``statement`` here only ever carries the text the
Data agent proposes or the tool actually ran — enforcing that it is
``SELECT``-only against a read-only role is tool-adapter logic (AGENTS.md),
not a concern of this schema."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.agents import Evidence


class DataQueryInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    target_schema: str | None = Field(default=None, max_length=200)


class DataQueryResult(BaseModel):
    statement: str = Field(min_length=1)
    columns: list[str] = Field(default_factory=list)
    row_count: int = Field(ge=0)
    rows: list[dict[str, str | int | float | bool | None]] = Field(default_factory=list)
    duration_ms: int = Field(ge=0, default=0)
    evidence: list[Evidence] = Field(default_factory=list)
