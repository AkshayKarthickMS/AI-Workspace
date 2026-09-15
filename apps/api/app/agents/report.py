from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.llm.base import LLMProvider
from app.schemas.agents import AgentRole, FinalReport, Finding, Mission, Slide, SlideDeck
from app.schemas.compliance import ComplianceReviewResult, ComplianceVerdict
from app.schemas.qa import QAResult

_MAX_SLIDE_BULLETS = 8
_MAX_RECOMMENDATIONS = 6

_NARRATIVE_SYSTEM_PROMPT = (
    "You are a senior business analyst writing the executive summary and "
    "recommendations section of a report for company leadership. You are given "
    "a mission objective and a list of VERIFIED, evidence-backed findings that "
    "have already passed fact-checking -- treat every one of them as true. "
    "Write a concise executive summary (3-5 sentences) that synthesizes what "
    "these findings mean for the business, citing specific numbers from the "
    "findings rather than restating them generically. Then write up to "
    f"{_MAX_RECOMMENDATIONS} specific, actionable recommendations -- each one "
    "must say what the business should DO in response to a specific finding, "
    "not just restate the finding. Do not invent any fact, number, or finding "
    "that is not listed below; if the findings are too thin to say anything "
    "meaningful, say so plainly instead of inventing content. Reply with JSON "
    "only."
)


class _Narrative(BaseModel):
    executive_summary: str = Field(min_length=1, max_length=2000)
    recommendations: list[str] = Field(default_factory=list, max_length=_MAX_RECOMMENDATIONS)


class ReportAgent(BaseAgent[FinalReport]):
    """Assembles the executive report and slide deck strictly from QA-cleared
    and Compliance-cleared findings (ARCHITECTURE.md section 7). Both gates
    are enforced here too, not only by graph routing -- defense in depth per
    AGENTS.md ("agents ... cannot bypass ... required approvals"). The
    narrative (executive summary + recommendations) is LLM-authored, but only
    ever synthesizes the already-verified findings below it -- it never sees
    raw data or an unverified claim, so it can't introduce a new fact, only
    explain what the cleared ones mean and what to do about them."""

    role = AgentRole.REPORT

    def __init__(self, llm: LLMProvider, audit: AuditSink | None = None) -> None:
        super().__init__(audit)
        self.llm = llm

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
        narrative = self.llm.complete(
            system=_NARRATIVE_SYSTEM_PROMPT,
            prompt=self._findings_prompt(mission, facts),
            response_model=_Narrative,
            max_retries=2,
            run_id=run_id,
            task_id=task_id,
        )

        return FinalReport(
            mission_id=mission.mission_id,
            title=f"Executive report: {mission.objective[:80]}",
            executive_summary=narrative.executive_summary,
            facts=facts,
            recommendations=narrative.recommendations,
            evidence=qa_result.evidence,
            qa_status=qa_result.status,
            compliance_verdict=compliance_result.verdict,
            slide_deck=self._build_slide_deck(mission, facts, narrative.recommendations),
        )

    @staticmethod
    def _findings_prompt(mission: Mission, facts: list[Finding]) -> str:
        lines = [f"Mission objective: {mission.objective}"]
        if mission.success_criteria:
            lines.append(f"Success criteria: {'; '.join(mission.success_criteria)}")
        if not facts:
            lines.append("Verified findings: none were produced.")
            return "\n".join(lines)
        lines.append("Verified findings:")
        lines.extend(f"- [{finding.category}] {finding.statement}" for finding in facts)
        return "\n".join(lines)

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
