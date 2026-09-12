import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from app.agents.base import AgentInvocationError, BaseAgent
from app.agents.data_analyst import DataAnalystAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.report import ReportAgent
from app.agents.research import ResearchAgent
from app.agents.verification import VerificationAgent
from app.events.audit import AuditSink
from app.schemas.agents import (
    AgentResult,
    AgentRole,
    Mission,
    Evidence,
    TaskStatus,
    VerificationResult,
)
from app.tools.data_analysis import PandasSalesAnalysisTool
from app.tools.research import ControlledResearchTool
from app.workflows.state import AegisState

logger = logging.getLogger(__name__)


class AegisRuntime:
    """Compile and execute the bounded AegisOS LangGraph workflow."""

    def __init__(
        self,
        data_root: Path,
        research_sources: Iterable[Evidence] = (),
        max_retries: int = 1,
        audit: AuditSink | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.audit = audit or AuditSink()
        self.orchestrator = OrchestratorAgent(self.audit)
        self.research = ResearchAgent(ControlledResearchTool(research_sources), self.audit)
        self.data_analyst = DataAnalystAgent(PandasSalesAnalysisTool(data_root), self.audit)
        self.verification = VerificationAgent(self.audit)
        self.report = ReportAgent(self.audit)
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(AegisState)
        graph.add_node("orchestrate", self._orchestrate)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("research", self._run_research)
        graph.add_node("data_analyst", self._run_data_analyst)
        graph.add_node("verification", self._run_verification)
        graph.add_node("report", self._run_report)
        graph.add_edge(START, "orchestrate")
        graph.add_edge("orchestrate", "dispatch")
        graph.add_conditional_edges(
            "dispatch",
            self._route,
            {
                "research": "research",
                "data_analyst": "data_analyst",
                "verification": "verification",
                "report": "report",
                "end": END,
            },
        )
        for node in ("research", "data_analyst", "verification", "report"):
            graph.add_edge(node, "dispatch")
        return graph.compile()

    def _orchestrate(self, state: AegisState) -> dict[str, Any]:
        mission = state["mission"]
        run_id = state["run_id"]
        plan = self.orchestrator.invoke(mission, run_id)
        tasks = {task.task_id: task for task in plan.tasks}
        self.audit.emit(
            self._event(
                "workflow.plan.created",
                mission,
                run_id,
                "completed",
                {"task_count": len(tasks)},
            )
        )
        return {"plan": plan, "tasks": tasks, "status": "planned", "retry_counts": {}}

    def _dispatch(self, state: AegisState) -> dict[str, Any]:
        tasks = state["tasks"]
        completed = {
            task.task_id for task in tasks.values() if task.status == TaskStatus.COMPLETED
        }
        for task in tasks.values():
            if task.status == TaskStatus.PENDING and all(dep in completed for dep in task.dependencies):
                updated = task.model_copy(update={"status": TaskStatus.RUNNING})
                return {
                    "tasks": {**tasks, task.task_id: updated},
                    "current_task_id": task.task_id,
                    "status": "running",
                }
        if all(task.status == TaskStatus.COMPLETED for task in tasks.values()):
            return {"status": "completed", "current_task_id": None}
        if any(task.status == TaskStatus.FAILED for task in tasks.values()):
            return {"status": "failed", "current_task_id": None}
        return {"status": "failed", "current_task_id": None, "errors": ["No runnable task remains"]}

    def _route(self, state: AegisState) -> str:
        if state.get("status") in {"completed", "failed"}:
            return "end"
        task_id = state.get("current_task_id")
        if task_id is None:
            raise RuntimeError("Routing requires a current task")
        task = state["tasks"][task_id]
        return task.agent.value

    def _run_research(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.RESEARCH, self.research)

    def _run_data_analyst(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.DATA_ANALYST, self.data_analyst)

    def _run_verification(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.VERIFICATION, self.verification)

    def _run_report(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.REPORT, self.report)

    def _run_task(
        self, state: AegisState, role: AgentRole, agent: BaseAgent[Any]
    ) -> dict[str, Any]:
        task_id = state["current_task_id"]
        if task_id is None:
            raise RuntimeError("Task execution requires a current task")
        task = state["tasks"][task_id]
        mission = state["mission"]
        run_id = state["run_id"]
        context = dict(task.input)
        if role == AgentRole.VERIFICATION:
            context["findings"] = [
                finding.model_dump(mode="json")
                for result in state["results"].values()
                for finding in result.findings
            ]
        elif role == AgentRole.REPORT:
            context["findings"] = [
                finding.model_dump(mode="json")
                for result in state["results"].values()
                for finding in result.findings
            ]
            verification = state.get("verification")
            if verification is None:
                raise RuntimeError("Report execution requires verification output")
            context["verification"] = verification.model_dump(mode="json")
        elif role == AgentRole.DATA_ANALYST and not context.get("dataset_path"):
            context["dataset_path"] = mission.context.get("dataset_path", "")
        retry_counts = dict(state.get("retry_counts", {}))
        try:
            result = agent.invoke(mission, run_id, task_id, context)
        except AgentInvocationError as exc:
            retries = retry_counts.get(task_id, 0)
            if retries < self.max_retries:
                retry_counts[task_id] = retries + 1
                retry_task = task.model_copy(
                    update={"status": TaskStatus.PENDING, "error": str(exc)}
                )
                return {
                    "tasks": {**state["tasks"], task_id: retry_task},
                    "retry_counts": retry_counts,
                }
            failed_task = task.model_copy(update={"status": TaskStatus.FAILED, "error": str(exc)})
            return {
                "tasks": {**state["tasks"], task_id: failed_task},
                "retry_counts": retry_counts,
                "status": "failed",
                "errors": [*state.get("errors", []), str(exc)],
            }

        updates: dict[str, Any] = {
            "tasks": {
                **state["tasks"],
                task_id: task.model_copy(
                    update={
                        "status": TaskStatus.COMPLETED,
                        "result_id": getattr(result, "result_id", None),
                    }
                ),
            },
            "current_task_id": None,
            "retry_counts": retry_counts,
        }
        if isinstance(result, AgentResult):
            updates["results"] = {**state.get("results", {}), result.result_id: result}
        elif isinstance(result, VerificationResult):
            updates["verification"] = result
        else:
            updates["final_report"] = result
        return updates

    def _event(
        self,
        event_type: str,
        mission: Mission,
        run_id: UUID,
        status: str,
        metadata: dict[str, str | int | float | bool | None],
    ) -> Any:
        from app.events.audit import AuditEvent

        return AuditEvent(
            event_type=event_type,
            actor=AgentRole.ORCHESTRATOR.value,
            mission_id=mission.mission_id,
            run_id=run_id,
            status=status,
            metadata=metadata,
        )

    def run(self, mission: Mission, run_id: UUID | None = None) -> AegisState:
        run_id = run_id or uuid4()
        initial: AegisState = {
            "mission": mission,
            "run_id": run_id,
            "results": {},
            "audit_events": [],
            "retry_counts": {},
            "errors": [],
            "status": "running",
        }
        final_state = cast(AegisState, self.graph.invoke(initial, config={"recursion_limit": 50}))
        final_state["audit_events"] = list(self.audit.events)
        return final_state


def build_runtime(data_root: Path) -> AegisRuntime:
    return AegisRuntime(data_root=data_root)
