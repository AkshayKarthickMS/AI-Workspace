from typing import Any, Literal
from uuid import UUID

from app.agents.base import BaseAgent
from app.schemas.agents import AgentRole, Finding, Mission, VerificationResult


class VerificationAgent(BaseAgent[VerificationResult]):
    role = AgentRole.VERIFICATION

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> VerificationResult:
        findings = [Finding.model_validate(item) for item in context.get("findings", [])]
        unsupported = [finding.statement for finding in findings if not finding.evidence]
        corrections = []
        if not findings:
            corrections.append("No findings were produced; collect evidence before reporting.")
        if unsupported:
            corrections.append("Remove or source every claim without attached evidence.")
        status: Literal["PASS", "FAIL"] = "FAIL" if unsupported or not findings else "PASS"
        evidence = [evidence for finding in findings for evidence in finding.evidence]
        return VerificationResult(
            status=status,
            checked_findings=[finding.finding_id for finding in findings],
            unsupported_claims=unsupported,
            corrections=corrections,
            evidence=evidence,
        )
