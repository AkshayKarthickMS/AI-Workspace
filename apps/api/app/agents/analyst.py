from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.schemas.agents import AgentResult, AgentRole, Evidence, Finding, Mission
from app.schemas.code_execution import CodeExecutionInput
from app.tools.code_execution import CodeExecutionTool
from app.tools.tabular_analysis import GenericTabularAnalysisTool


class AnalystAgent(BaseAgent[AgentResult]):
    """Tabular analysis plus bounded, sandboxed code execution
    (ARCHITECTURE.md section 7). ``code_tool`` is optional: a plan that only
    needs the prebuilt tabular analysis never has to touch the sandbox."""

    role = AgentRole.ANALYST

    def __init__(
        self,
        tabular_tool: GenericTabularAnalysisTool,
        code_tool: CodeExecutionTool | None = None,
        audit: AuditSink | None = None,
    ) -> None:
        super().__init__(audit)
        self.tabular_tool = tabular_tool
        self.code_tool = code_tool

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> AgentResult:
        dataset_path = str(context.get("dataset_path") or mission.context.get("dataset_path", ""))
        findings: list[Finding] = []
        evidence: list[Evidence] = []
        summary: dict[str, Any] = {}

        if dataset_path:
            tabular_findings, tabular_evidence, tabular_summary = self.tabular_tool.analyze(
                dataset_path
            )
            findings.extend(tabular_findings)
            evidence.extend(tabular_evidence)
            summary.update(tabular_summary)

        code = context.get("code")
        if code and self.code_tool is not None:
            code_findings, code_evidence, code_summary = self._run_code(str(code), dataset_path)
            findings.extend(code_findings)
            evidence.extend(code_evidence)
            summary.update(code_summary)

        if not findings:
            raise ValueError("Analyst agent requires a dataset_path and/or code to analyze")

        return AgentResult(
            agent=self.role, status="success", findings=findings, evidence=evidence, output=summary
        )

    def _run_code(
        self, code: str, dataset_path: str
    ) -> tuple[list[Finding], list[Evidence], dict[str, Any]]:
        assert self.code_tool is not None
        result = self.code_tool.execute(
            CodeExecutionInput(code=code, dataset_path=dataset_path or None)
        )
        code_evidence = Evidence(
            source="sandboxed_code_execution",
            source_type="dataset",
            locator=f"exit_status={result.exit_status}",
            excerpt=(result.stdout or result.stderr)[:500],
            metadata={"exit_status": result.exit_status, "timed_out": result.timed_out},
        )
        findings: list[Finding] = []
        if result.exit_status == 0 and not result.timed_out:
            findings.append(
                Finding(
                    statement="Custom analysis code executed successfully in the sandbox.",
                    category="fact",
                    confidence=0.8,
                    evidence=[code_evidence],
                    metrics={"duration_ms": result.duration_ms},
                )
            )
        return findings, [code_evidence], {"code_execution": result.model_dump(mode="json")}
