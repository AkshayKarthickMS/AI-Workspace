from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.schemas.agents import AgentResult, AgentRole, Mission
from app.tools.data_analysis import PandasSalesAnalysisTool


class DataAnalystAgent(BaseAgent[AgentResult]):
    role = AgentRole.DATA_ANALYST

    def __init__(self, tool: PandasSalesAnalysisTool, audit: AuditSink | None = None) -> None:
        super().__init__(audit)
        self.tool = tool

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> AgentResult:
        dataset_path = str(context.get("dataset_path") or mission.context.get("dataset_path", ""))
        findings, evidence, summary = self.tool.analyze(dataset_path)
        return AgentResult(
            agent=self.role,
            status="success",
            findings=findings,
            evidence=evidence,
            output=summary,
        )
