from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.schemas.agents import AgentResult, AgentRole, Finding, Mission
from app.tools.research import ControlledResearchTool


class ResearchAgent(BaseAgent[AgentResult]):
    role = AgentRole.RESEARCH

    def __init__(
        self, tool: ControlledResearchTool | None = None, audit: AuditSink | None = None
    ) -> None:
        super().__init__(audit)
        self.tool = tool or ControlledResearchTool()

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> AgentResult:
        query = str(context.get("query", mission.objective))
        evidence = self.tool.search(query)
        findings = []
        if evidence:
            findings = [
                Finding(
                    statement="Approved research evidence was retrieved for the mission.",
                    category="fact",
                    confidence=0.8,
                    evidence=evidence,
                )
            ]
        return AgentResult(
            agent=self.role,
            status="success",
            findings=findings,
            evidence=evidence,
            output={"sources_found": len(evidence), "source_policy": "approved evidence only"},
        )
