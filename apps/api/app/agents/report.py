from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.schemas.agents import AgentRole, FinalReport, Finding, Mission, VerificationResult


class ReportAgent(BaseAgent[FinalReport]):
    role = AgentRole.REPORT

    def __init__(self, audit: AuditSink | None = None) -> None:
        super().__init__(audit)

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> FinalReport:
        verification = VerificationResult.model_validate(context.get("verification", {}))
        findings = [Finding.model_validate(item) for item in context.get("findings", [])]
        if verification.status != "PASS":
            raise ValueError("Cannot create a final report from unverified findings")
        facts = [finding for finding in findings if finding.category != "recommendation"]
        recommendations = [
            f"Review operating actions related to: {finding.statement}"
            for finding in facts
            if finding.category in {"risk", "anomaly"}
        ]
        summary = (
            f"The analysis produced {len(facts)} verified findings for the mission. "
            "Recommendations are presented separately from observed facts."
        )
        return FinalReport(
            mission_id=mission.mission_id,
            title=f"Executive report: {mission.objective[:80]}",
            executive_summary=summary,
            facts=facts,
            recommendations=recommendations,
            evidence=verification.evidence,
            verification_status=verification.status,
        )
