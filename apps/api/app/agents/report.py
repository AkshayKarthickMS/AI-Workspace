from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.schemas.agents import AgentRole, FinalReport, Finding, Mission, Slide, SlideDeck
from app.schemas.compliance import ComplianceReviewResult, ComplianceVerdict
from app.schemas.qa import QAResult

_MAX_SLIDE_BULLETS = 8


class ReportAgent(BaseAgent[FinalReport]):
    """Assembles the executive report and slide deck strictly from QA-cleared
    and Compliance-cleared findings (ARCHITECTURE.md section 7). Both gates
    are enforced here too, not only by graph routing -- defense in depth per
    AGENTS.md ("agents ... cannot bypass ... required approvals")."""

    role = AgentRole.REPORT

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> FinalReport:
        qa_result = QAResult.model_validate(context.get("qa_result", {}))
        compliance_result = ComplianceReviewResult.model_validate(
            context.get("compliance_result", {})
        )
        findings = [Finding.model_validate(item) for item in context.get("findings", [])]

        if qa_result.status != "PASS":
            raise ValueError("Cannot create a final report from findings that failed QA")
        if compliance_result.verdict != ComplianceVerdict.PASS:
            raise ValueError("Cannot create a final report without Compliance clearance")

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
            evidence=qa_result.evidence,
            qa_status=qa_result.status,
            compliance_verdict=compliance_result.verdict,
            slide_deck=self._build_slide_deck(mission, facts, recommendations),
        )

    @staticmethod
    def _build_slide_deck(
        mission: Mission, facts: list[Finding], recommendations: list[str]
    ) -> SlideDeck:
        title = f"Executive report: {mission.objective[:80]}"
        slides = [
            Slide(title=title, bullets=[mission.objective[:200]]),
            Slide(
                title="Key facts",
                bullets=[finding.statement for finding in facts[:_MAX_SLIDE_BULLETS]]
                or ["No facts to report."],
            ),
        ]
        if recommendations:
            slides.append(
                Slide(title="Recommendations", bullets=recommendations[:_MAX_SLIDE_BULLETS])
            )
        return SlideDeck(title=title, slides=slides)
