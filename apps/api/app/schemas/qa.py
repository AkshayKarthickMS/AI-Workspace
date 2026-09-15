"""QA agent result contract: evidentiary support plus groundedness/hallucination
checks (ARCHITECTURE.md §7). Parallels the existing ``VerificationResult`` in
``app.schemas.agents`` rather than replacing it — the current VerificationAgent
keeps using that type until Phase 3 extends it into the QA agent."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.schemas.agents import Evidence


class QAResult(BaseModel):
    result_id: UUID = Field(default_factory=uuid4)
    status: Literal["PASS", "FAIL"]
    checked_findings: list[UUID] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    # finding_id (str) -> groundedness score in [0, 1]; empty until Phase 3 wires
    # the actual claim-vs-evidence comparison.
    groundedness_scores: dict[str, float] = Field(default_factory=dict)
    corrections: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
