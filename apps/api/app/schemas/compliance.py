"""Compliance agent verdict contract: the policy/PII/regulatory review gate that
must clear before the Report agent may assemble a deliverable (ARCHITECTURE.md
§7, §12)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ComplianceVerdict(StrEnum):
    PASS = "pass"
    ESCALATE = "escalate"
    REJECT = "reject"


class ComplianceReviewResult(BaseModel):
    result_id: UUID = Field(default_factory=uuid4)
    rule_set_version: str = Field(min_length=1, max_length=50)
    verdict: ComplianceVerdict
    reviewed_finding_ids: list[UUID] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    escalation_reason: str | None = Field(default=None, max_length=1000)
