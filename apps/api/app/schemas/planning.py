"""LLM-facing plan-draft contract (ARCHITECTURE.md section 7). The model only
ever chooses which gathering agents (research/data/analyst) a mission needs
and drafts their inputs -- it cannot omit or reorder the QA, Compliance, and
Report gates, which OrchestratorAgent appends deterministically. This keeps
"Agents can propose actions but cannot bypass ... required approvals"
(AGENTS.md) true even though the plan itself is now LLM-authored."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DraftTask(BaseModel):
    agent: Literal["research", "data", "analyst"]
    description: str = Field(min_length=1, max_length=1000)
    input: dict[str, Any] = Field(default_factory=dict)


class DraftPlan(BaseModel):
    rationale: str = Field(min_length=1, max_length=2000)
    tasks: list[DraftTask] = Field(min_length=1, max_length=3)
