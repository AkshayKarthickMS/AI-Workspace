"""Durable, resumable LangGraph runtime for a single AegisOS execution."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.analyst import AnalystAgent
from app.agents.base import AgentInvocationError, BaseAgent
from app.agents.compliance import ComplianceAgent
from app.agents.data import DataAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.qa import QAAgent
from app.agents.report import ReportAgent
from app.agents.research import ResearchAgent
from app.core.config import get_settings
from app.core.redaction import redact
from app.db.session import session_scope
from app.events.audit import AuditEvent, AuditSink, CompositeAuditSink
from app.events.redis_bus import RedisEventBusSink
from app.llm.base import LLMProvider
from app.llm.factory import build_traced_llm_provider
from app.retrieval.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from app.retrieval.search import HybridSearchService
from app.schemas.agents import (
    AgentResult,
    AgentRole,
    Evidence,
    FinalReport,
    Mission,
    Task,
    TaskStatus,
)
from app.schemas.compliance import ComplianceReviewResult, ComplianceVerdict
from app.schemas.qa import QAResult
from app.tools.code_execution import CodeExecutionTool
from app.tools.research import ControlledResearchTool
from app.tools.sql_query import TextToSqlTool
from app.tools.tabular_analysis import GenericTabularAnalysisTool
from app.workflows.checkpoints import (
    CheckpointCorruptError,
    CheckpointError,
    CheckpointNotFoundError,
    RuntimeCheckpointStore,
)
from app.workflows.state import (
    MAX_STATE_EVENT_LIMIT,
    AegisState,
    AgentExecutionStatus,
    ApprovalStatus,
    ExecutionStatus,
    JsonObject,
    append_recent_event,
    build_initial_state,
    build_structured_error,
    deserialize_state,
    serialize_datetime,
    serialize_state,
)

logger = logging.getLogger(__name__)
_TERMINAL_STATUSES = {
    ExecutionStatus.CANCELLED,
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
}
# Statuses where the run is deliberately not advancing: a generic debug pause
# (PAUSED) or one of the two mandatory human-in-the-loop gates. Dispatch must
# never act while in any of these.
_HELD_STATUSES = {
    ExecutionStatus.PAUSED,
    ExecutionStatus.AWAITING_APPROVAL,
    ExecutionStatus.AWAITING_ESCALATION,
}
_GATHERING_ROLES = {AgentRole.RESEARCH.value, AgentRole.DATA.value, AgentRole.ANALYST.value}


class AegisRuntime:
    """Compile and execute the bounded AegisOS LangGraph workflow.

    Pydantic models are reconstructed only at node boundaries. The graph and the
    SQLite LangGraph checkpointer receive the JSON-only ``AegisState`` payload.

    Graph shape (ARCHITECTURE.md section 7)::

        plan -> await_approval -> dispatch -> {research|data|analyst}
             -> dispatch -> qa -> (retry -> dispatch | replan -> await_approval | compliance)
             -> compliance -> (escalate_approval | report)
             -> report -> dispatch (all tasks complete -> finalize)

    "intake" is the mission validation `build_initial_state` already performs
    before the graph starts; there is no separate intake node. "finalize" is
    `_dispatch` noticing every task is complete, not a dedicated node either.
    """

    def __init__(
        self,
        data_root: Path,
        research_sources: Iterable[Evidence] = (),
        max_retries: int = 1,
        audit: AuditSink | None = None,
        checkpoint_path: Path | None = None,
        max_state_events: int = 25,
        interrupt_after: Iterable[str] = (),
        *,
        llm: LLMProvider | None = None,
        embeddings: EmbeddingProvider | None = None,
        sql_session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
        search: HybridSearchService | None = None,
        workspace_id: UUID | None = None,
        redis_client: Any | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if not 1 <= max_state_events <= MAX_STATE_EVENT_LIMIT:
            raise ValueError(f"max_state_events must be between 1 and {MAX_STATE_EVENT_LIMIT}")

        settings = get_settings()
        self.max_retries = max_retries
        self.max_state_events = max_state_events
        if audit is not None:
            self.audit = audit
        elif redis_client is not None:
            self.audit = CompositeAuditSink([RedisEventBusSink(redis_client)])
        else:
            self.audit = AuditSink()
        self.checkpoints = RuntimeCheckpointStore(
            checkpoint_path or data_root.parent / "runtime-checkpoints.sqlite"
        )
        # await_approval/escalate_approval are mandatory gates (ARCHITECTURE.md:
        # "Require human approval before execution by default") - always
        # included regardless of what the caller passes here, which remains
        # available for additional custom pause points (e.g. tests).
        self.interrupt_after = tuple(
            dict.fromkeys([*interrupt_after, "await_approval", "escalate_approval"])
        )

        # Local/open-weight providers only (AGENTS.md). Callers inject fakes in
        # tests; production defaults come from Settings so `AegisRuntime()`
        # just works against the configured local model stack, with Langfuse
        # tracing applied automatically when configured (ARCHITECTURE.md §11).
        self.llm = llm or build_traced_llm_provider(settings)
        self.embeddings = embeddings or OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url, model=settings.embedding_model_name
        )
        sql_session_factory = sql_session_factory or session_scope

        self.orchestrator = OrchestratorAgent(self.llm, self.audit)
        self.research = ResearchAgent(
            ControlledResearchTool(research_sources, retrieval=search, workspace_id=workspace_id),
            self.audit,
        )
        self.data = DataAgent(self.llm, TextToSqlTool(sql_session_factory), self.audit)
        self.analyst = AnalystAgent(
            GenericTabularAnalysisTool(data_root),
            CodeExecutionTool(
                timeout_seconds=settings.sandbox_timeout_seconds,
                memory_limit_mb=settings.sandbox_memory_limit_mb,
                cpu_limit=settings.sandbox_cpu_limit,
            ),
            self.audit,
        )
        self.qa = QAAgent(self.llm, self.embeddings, self.audit)
        self.compliance = ComplianceAgent(self.audit)
        self.report = ReportAgent(self.audit)
        self.graph = self._build_graph()

    def __enter__(self) -> AegisRuntime:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Release the local SQLite connection when the runtime is no longer used."""

        self.checkpoints.close()

    def _build_graph(self) -> Any:
        graph = StateGraph(AegisState)
        graph.add_node("plan", self._plan)
        graph.add_node("await_approval", self._await_approval)
        graph.add_node("dispatch", self._dispatch)
        graph.add_node("research", self._run_research)
        graph.add_node("data", self._run_data)
        graph.add_node("analyst", self._run_analyst)
        graph.add_node("qa", self._run_qa)
        graph.add_node("compliance", self._run_compliance)
        graph.add_node("escalate_approval", self._escalate_approval)
        graph.add_node("report", self._run_report)
        graph.add_node("cancel", self._cancel)

        graph.add_edge(START, "plan")
        graph.add_edge("plan", "await_approval")
        graph.add_conditional_edges(
            "await_approval",
            self._route_after_approval,
            {
                "dispatch": "dispatch",
                "await_approval": "await_approval",
                "cancel": "cancel",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "dispatch",
            self._route,
            {
                "research": "research",
                "data": "data",
                "analyst": "analyst",
                "qa": "qa",
                "compliance": "compliance",
                "report": "report",
                "cancel": "cancel",
                "end": END,
            },
        )
        for node in ("research", "data", "analyst", "report"):
            graph.add_edge(node, "dispatch")
        graph.add_conditional_edges(
            "qa",
            self._route_after_qa,
            {
                "dispatch": "dispatch",
                "await_approval": "await_approval",
                "cancel": "cancel",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "compliance",
            self._route_after_compliance,
            {
                "dispatch": "dispatch",
                "escalate_approval": "escalate_approval",
                "cancel": "cancel",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "escalate_approval",
            self._route_after_escalation,
            {
                "dispatch": "dispatch",
                "escalate_approval": "escalate_approval",
                "cancel": "cancel",
                "end": END,
            },
        )
        graph.add_edge("cancel", END)
        return graph.compile(
            checkpointer=self.checkpoints.saver,
            interrupt_after=list(self.interrupt_after),
        )

    def _plan(self, state: AegisState) -> dict[str, Any]:
        mission = self._mission(state)
        execution_id = self._execution_id(state)
        plan = self.orchestrator.invoke(mission, execution_id)
        tasks = {str(task.task_id): self._dump_model(task) for task in plan.tasks}
        statuses = {
            str(task.task_id): AgentExecutionStatus.PENDING.value for task in plan.tasks
        }
        recent_events = self._record_transition(
            state,
            "workflow.plan.created",
            "completed",
            metadata={"task_count": len(tasks)},
        )
        return {
            "plan": self._dump_model(plan),
            "tasks": tasks,
            "retry_counts": {},
            "agent_statuses": statuses,
            "recent_events": recent_events,
            "status": ExecutionStatus.RUNNING.value,
        }

    def _await_approval(self, state: AegisState) -> dict[str, Any]:
        if ExecutionStatus(state["status"]) == ExecutionStatus.CANCEL_REQUESTED:
            return {"current_task_id": None}
        approval = state.get("approval")
        if approval is None:
            approval = {
                "status": ApprovalStatus.PENDING.value,
                "reason": "initial_plan",
                "requested_at": serialize_datetime(datetime.now(UTC)),
            }
            recent_events = self._record_transition(state, "plan.approval.requested", "pending")
            return {
                "approval": approval,
                "status": ExecutionStatus.AWAITING_APPROVAL.value,
                "recent_events": recent_events,
            }
        if approval.get("status") == ApprovalStatus.PENDING.value:
            # Re-entered via the self-loop below (a defensive premature
            # resume): resume() may have forced status back to RUNNING before
            # re-entering the graph, so restate it here.
            return {"status": ExecutionStatus.AWAITING_APPROVAL.value}
        return {}

    def _route_after_approval(self, state: AegisState) -> str:
        status = ExecutionStatus(state["status"])
        if status in _TERMINAL_STATUSES:
            return "end"
        if status == ExecutionStatus.CANCEL_REQUESTED:
            return "cancel"
        approval = state.get("approval") or {}
        if approval.get("status") == ApprovalStatus.APPROVED.value:
            return "dispatch"
        return "await_approval"

    def _dispatch(self, state: AegisState) -> dict[str, Any]:
        status = ExecutionStatus(state["status"])
        if status in _TERMINAL_STATUSES or status in _HELD_STATUSES:
            return {}
        if status == ExecutionStatus.CANCEL_REQUESTED:
            return {"current_task_id": None}

        tasks = self._tasks(state)
        completed = {
            task.task_id for task in tasks.values() if task.status == TaskStatus.COMPLETED
        }
        for task in tasks.values():
            if task.status == TaskStatus.PENDING and all(
                dependency in completed for dependency in task.dependencies
            ):
                updated = task.model_copy(update={"status": TaskStatus.RUNNING, "error": None})
                task_id = str(task.task_id)
                recent_events = self._record_transition(
                    state,
                    "task.started",
                    "started",
                    task_id=task.task_id,
                    metadata={"agent": task.agent.value},
                )
                return {
                    "tasks": {**state["tasks"], task_id: self._dump_model(updated)},
                    "current_task_id": task_id,
                    "agent_statuses": {
                        **state.get("agent_statuses", {}),
                        task_id: AgentExecutionStatus.RUNNING.value,
                    },
                    "recent_events": recent_events,
                    "status": ExecutionStatus.RUNNING.value,
                }

        if all(task.status == TaskStatus.COMPLETED for task in tasks.values()):
            recent_events = self._record_transition(state, "execution.completed", "completed")
            return {
                "status": ExecutionStatus.COMPLETED.value,
                "current_task_id": None,
                "recent_events": recent_events,
            }
        if any(task.status == TaskStatus.FAILED for task in tasks.values()):
            return {"status": ExecutionStatus.FAILED.value, "current_task_id": None}

        error = build_structured_error(
            "SchedulingError", "No runnable task remains for this execution."
        )
        task_events = self._record_transition(state, "execution.failed", "failed")
        return {
            "status": ExecutionStatus.FAILED.value,
            "current_task_id": None,
            "last_error": error,
            "recent_events": task_events,
        }

    def _route(self, state: AegisState) -> str:
        status = ExecutionStatus(state["status"])
        if status in _TERMINAL_STATUSES or status in _HELD_STATUSES:
            return "end"
        if status == ExecutionStatus.CANCEL_REQUESTED:
            return "cancel"
        task_id = state.get("current_task_id")
        if task_id is None:
            raise RuntimeError("Routing requires a current task")
        task = Task.model_validate(state["tasks"][task_id])
        return task.agent.value

    def _cancel(self, state: AegisState) -> dict[str, Any]:
        task_updates = dict(state["tasks"])
        agent_statuses = dict(state.get("agent_statuses", {}))
        for task_id, task in self._tasks(state).items():
            if task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                task_updates[str(task_id)] = self._dump_model(
                    task.model_copy(update={"status": TaskStatus.CANCELLED})
                )
                agent_statuses[str(task_id)] = AgentExecutionStatus.CANCELLED.value
        recent_events = self._record_transition(state, "execution.cancelled", "cancelled")
        return {
            "tasks": task_updates,
            "agent_statuses": agent_statuses,
            "current_task_id": None,
            "recent_events": recent_events,
            "status": ExecutionStatus.CANCELLED.value,
        }

    def _run_research(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.RESEARCH, self.research)

    def _run_data(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.DATA, self.data)

    def _run_analyst(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.ANALYST, self.analyst)

    def _run_qa(self, state: AegisState) -> dict[str, Any]:
        updates = self._run_task(state, AgentRole.QA, self.qa)
        qa_data = updates.get("qa_result")
        if qa_data is None or qa_data["status"] == "PASS":
            return updates

        # QA FAIL: bounded retry of the gathering phase (research/data/analyst
        # + QA itself, reset to PENDING), then -- if retries are exhausted --
        # a "replan" gate: require a human to re-approve before the (unchanged)
        # plan is retried again. Full automatic re-planning via a second LLM
        # call is out of scope here; a human re-approving is the safety valve.
        merged = cast(AegisState, {**state, **updates})
        reset = self._reset_gathering_phase(merged)
        qa_retry_count = int(state.get("qa_retry_count", 0))
        if qa_retry_count < self.max_retries:
            recent_events = self._record_transition(
                merged,
                "qa.retry.started",
                "retrying",
                metadata={"qa_retry_count": qa_retry_count + 1},
            )
            return {
                **updates,
                **reset,
                "qa_retry_count": qa_retry_count + 1,
                "recent_events": recent_events,
            }

        approval = {
            "status": ApprovalStatus.PENDING.value,
            "reason": "qa_failed_after_retries",
            "requested_at": serialize_datetime(datetime.now(UTC)),
        }
        recent_events = self._record_transition(
            merged, "execution.replan_required", "awaiting_approval"
        )
        return {
            **updates,
            **reset,
            "approval": approval,
            "status": ExecutionStatus.AWAITING_APPROVAL.value,
            "recent_events": recent_events,
        }

    def _reset_gathering_phase(self, state: AegisState) -> dict[str, Any]:
        """Reset research/data/analyst/QA tasks to PENDING and drop their
        stale results, so a fresh dispatch cycle re-runs them."""

        tasks = dict(state["tasks"])
        results = dict(state.get("results", {}))
        agent_statuses = dict(state.get("agent_statuses", {}))
        reset_roles = {*_GATHERING_ROLES, AgentRole.QA.value}
        for task_id, task_data in state["tasks"].items():
            if task_data.get("agent") in reset_roles:
                result_id = task_data.get("result_id")
                if isinstance(result_id, str) and result_id in results:
                    del results[result_id]
                tasks[task_id] = {
                    **task_data,
                    "status": TaskStatus.PENDING.value,
                    "result_id": None,
                    "error": None,
                }
                agent_statuses[task_id] = AgentExecutionStatus.PENDING.value
        return {
            "tasks": tasks,
            "results": results,
            "agent_statuses": agent_statuses,
            "qa_result": None,
        }

    def _route_after_qa(self, state: AegisState) -> str:
        status = ExecutionStatus(state["status"])
        if status in _TERMINAL_STATUSES:
            return "end"
        if status == ExecutionStatus.CANCEL_REQUESTED:
            return "cancel"
        if status == ExecutionStatus.AWAITING_APPROVAL:
            return "await_approval"
        return "dispatch"

    def _run_compliance(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.COMPLIANCE, self.compliance)

    def _route_after_compliance(self, state: AegisState) -> str:
        status = ExecutionStatus(state["status"])
        if status in _TERMINAL_STATUSES:
            return "end"
        if status == ExecutionStatus.CANCEL_REQUESTED:
            return "cancel"
        compliance_data = state.get("compliance_result")
        if compliance_data is not None and compliance_data.get("verdict") != (
            ComplianceVerdict.PASS.value
        ):
            return "escalate_approval"
        return "dispatch"

    def _escalate_approval(self, state: AegisState) -> dict[str, Any]:
        if ExecutionStatus(state["status"]) == ExecutionStatus.CANCEL_REQUESTED:
            return {"current_task_id": None}
        escalation = state.get("escalation")
        if escalation is None:
            compliance_data = state.get("compliance_result") or {}
            escalation = {
                "status": ApprovalStatus.PENDING.value,
                "reason": compliance_data.get("escalation_reason"),
                "violations": compliance_data.get("violations", []),
                "requested_at": serialize_datetime(datetime.now(UTC)),
            }
            recent_events = self._record_transition(
                state, "compliance.escalation.requested", "pending"
            )
            return {
                "escalation": escalation,
                "status": ExecutionStatus.AWAITING_ESCALATION.value,
                "recent_events": recent_events,
            }
        if escalation.get("status") == ApprovalStatus.PENDING.value:
            # Defensive premature resume, same reasoning as _await_approval.
            return {"status": ExecutionStatus.AWAITING_ESCALATION.value}
        return {}

    def _route_after_escalation(self, state: AegisState) -> str:
        status = ExecutionStatus(state["status"])
        if status in _TERMINAL_STATUSES:
            return "end"
        if status == ExecutionStatus.CANCEL_REQUESTED:
            return "cancel"
        escalation = state.get("escalation") or {}
        if escalation.get("status") == ApprovalStatus.APPROVED.value:
            return "dispatch"
        return "escalate_approval"

    def _run_report(self, state: AegisState) -> dict[str, Any]:
        return self._run_task(state, AgentRole.REPORT, self.report)

    def _run_task(
        self, state: AegisState, role: AgentRole, agent: BaseAgent[Any]
    ) -> dict[str, Any]:
        if ExecutionStatus(state["status"]) == ExecutionStatus.CANCEL_REQUESTED:
            return {"current_task_id": None}

        task_id = state.get("current_task_id")
        if task_id is None:
            raise RuntimeError("Task execution requires a current task")
        task = Task.model_validate(state["tasks"][task_id])
        if task.status == TaskStatus.COMPLETED:
            return {"current_task_id": None}
        if task.agent != role:
            raise RuntimeError("Task routing did not match the assigned agent role")

        mission = self._mission(state)
        execution_id = self._execution_id(state)
        context = self._build_context(state, role, mission, task)

        retry_counts = dict(state.get("retry_counts", {}))
        agent_statuses = dict(state.get("agent_statuses", {}))
        try:
            result = agent.invoke(mission, execution_id, task.task_id, context)
        except AgentInvocationError as exc:
            error = build_structured_error(
                type(exc).__name__,
                self._safe_error_message(exc),
                task_id=task.task_id,
                agent=role.value,
            )
            task_errors = {**state.get("task_errors", {}), task_id: error}
            retries = retry_counts.get(task_id, 0)
            if retries < self.max_retries:
                retry_counts[task_id] = retries + 1
                retry_task = task.model_copy(
                    update={"status": TaskStatus.PENDING, "error": str(error["message"])}
                )
                recent_events = self._record_transition(
                    state,
                    "task.retry.started",
                    "retrying",
                    task_id=task.task_id,
                    metadata={"retry_count": retry_counts[task_id], "agent": role.value},
                )
                return {
                    "tasks": {**state["tasks"], task_id: self._dump_model(retry_task)},
                    "current_task_id": None,
                    "retry_counts": retry_counts,
                    "agent_statuses": {
                        **agent_statuses,
                        task_id: AgentExecutionStatus.RETRYING.value,
                    },
                    "task_errors": task_errors,
                    "last_error": error,
                    "recent_events": recent_events,
                }

            failed_task = task.model_copy(
                update={"status": TaskStatus.FAILED, "error": str(error["message"])}
            )
            recent_events = self._record_transition(
                state,
                "task.failed",
                "failed",
                task_id=task.task_id,
                metadata={"agent": role.value},
            )
            event_state = cast(AegisState, {**state, "recent_events": recent_events})
            recent_events = self._record_transition(
                event_state,
                "execution.failed",
                "failed",
                metadata={"task_id": task_id},
            )
            return {
                "tasks": {**state["tasks"], task_id: self._dump_model(failed_task)},
                "current_task_id": None,
                "retry_counts": retry_counts,
                "agent_statuses": {
                    **agent_statuses,
                    task_id: AgentExecutionStatus.FAILED.value,
                },
                "task_errors": task_errors,
                "last_error": error,
                "recent_events": recent_events,
                "status": ExecutionStatus.FAILED.value,
            }

        completed_task = task.model_copy(
            update={"status": TaskStatus.COMPLETED, "result_id": getattr(result, "result_id", None)}
        )
        recent_events = self._record_transition(
            state,
            "task.completed",
            "completed",
            task_id=task.task_id,
            metadata={"agent": role.value},
        )
        updates: dict[str, Any] = {
            "tasks": {**state["tasks"], task_id: self._dump_model(completed_task)},
            "current_task_id": None,
            "retry_counts": retry_counts,
            "agent_statuses": {
                **agent_statuses,
                task_id: AgentExecutionStatus.COMPLETED.value,
            },
            "recent_events": recent_events,
        }
        if isinstance(result, AgentResult):
            updates["results"] = {
                **state.get("results", {}),
                str(result.result_id): self._dump_model(result),
            }
        elif isinstance(result, QAResult):
            updates["qa_result"] = self._dump_model(result)
        elif isinstance(result, ComplianceReviewResult):
            updates["compliance_result"] = self._dump_model(result)
        elif isinstance(result, FinalReport):
            updates["final_report"] = self._dump_model(result)
        else:
            raise RuntimeError("Agent returned an unsupported result type")
        return updates

    def _build_context(
        self, state: AegisState, role: AgentRole, mission: Mission, task: Task
    ) -> dict[str, Any]:
        context = dict(task.input)
        results = self._results(state)

        if role in {AgentRole.QA, AgentRole.COMPLIANCE, AgentRole.REPORT}:
            context["findings"] = [
                finding.model_dump(mode="json")
                for result_id in sorted(results)
                for finding in results[result_id].findings
            ]
        if role in {AgentRole.COMPLIANCE, AgentRole.REPORT}:
            qa_data = state.get("qa_result")
            if qa_data is None:
                raise RuntimeError(f"{role.value} execution requires QA output")
            context["qa_result"] = qa_data
        if role == AgentRole.REPORT:
            compliance_data = state.get("compliance_result")
            if compliance_data is None:
                raise RuntimeError("Report execution requires Compliance output")
            context["compliance_result"] = compliance_data
        if role == AgentRole.DATA and not context.get("question"):
            context["question"] = mission.objective
        if role == AgentRole.ANALYST and not context.get("dataset_path"):
            context["dataset_path"] = mission.context.get("dataset_path", "")
        return context

    def _execute_graph(
        self, execution_id: UUID, initial_state: AegisState | None
    ) -> AegisState:
        config = self.checkpoints.config(execution_id)
        latest_state = initial_state
        try:
            for update in self.graph.stream(initial_state, config=config, stream_mode="updates"):
                node_name = next(iter(update), "unknown")
                latest_state = self._load_state(execution_id)
                self._emit_checkpoint_created(latest_state, node_name)
            state = self._load_state(execution_id)
        except sqlite3.DatabaseError as exc:
            self._emit_checkpoint_failure(latest_state, exc)
            raise CheckpointError("Checkpoint persistence failed") from exc

        snapshot = self.graph.get_state(config)
        if snapshot.next and ExecutionStatus(state["status"]) == ExecutionStatus.RUNNING:
            recent_events = self._record_transition(state, "execution.paused", "paused")
            self.graph.update_state(
                config,
                {"status": ExecutionStatus.PAUSED.value, "recent_events": recent_events},
            )
            state = self._load_state(execution_id)
        return state

    def _load_state(self, execution_id: UUID) -> AegisState:
        if not self.checkpoints.has_execution(execution_id):
            raise CheckpointNotFoundError("No checkpoint exists for this execution")
        try:
            snapshot = self.graph.get_state(self.checkpoints.config(execution_id))
            return deserialize_state(cast(Mapping[str, object], snapshot.values))
        except (sqlite3.DatabaseError, ValueError, TypeError) as exc:
            raise CheckpointCorruptError("Latest checkpoint state is invalid") from exc

    def _emit_checkpoint_created(self, state: AegisState, node_name: str) -> None:
        event = self._new_audit_event(
            state,
            "checkpoint.created",
            "completed",
            metadata={"node": node_name, "schema_version": state["schema_version"]},
        )
        self.audit.emit(event)

    def _emit_checkpoint_failure(self, state: AegisState | None, exc: Exception) -> None:
        if state is None:
            logger.exception("checkpoint_failed_without_runtime_state")
            return
        error = build_structured_error(type(exc).__name__, self._safe_error_message(exc))
        self.audit.emit(
            self._new_audit_event(
                state,
                "checkpoint.failed",
                "failed",
                metadata={"error_type": str(error["error_type"])},
            )
        )

    def _record_transition(
        self,
        state: AegisState,
        event_type: str,
        status: str,
        *,
        task_id: UUID | None = None,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[JsonObject]:
        event = self._new_audit_event(state, event_type, status, task_id=task_id, metadata=metadata)
        self.audit.emit(event)
        return append_recent_event(state, cast(JsonObject, event.model_dump(mode="json")))

    def _new_audit_event(
        self,
        state: AegisState,
        event_type: str,
        status: str,
        *,
        task_id: UUID | None = None,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            event_type=event_type,
            actor=AgentRole.ORCHESTRATOR.value,
            mission_id=UUID(state["mission_id"]),
            run_id=self._execution_id(state),
            task_id=task_id,
            status=status,
            metadata=metadata or {},
        )

    def _mission(self, state: AegisState) -> Mission:
        return Mission.model_validate(state["mission"])

    def _tasks(self, state: AegisState) -> dict[UUID, Task]:
        return {
            UUID(task_id): Task.model_validate(task_data)
            for task_id, task_data in state.get("tasks", {}).items()
        }

    def _results(self, state: AegisState) -> dict[str, AgentResult]:
        return {
            result_id: AgentResult.model_validate(result_data)
            for result_id, result_data in state.get("results", {}).items()
        }

    @staticmethod
    def _dump_model(model: Any) -> JsonObject:
        return cast(JsonObject, model.model_dump(mode="json"))

    @staticmethod
    def _execution_id(state: AegisState) -> UUID:
        return UUID(state["execution_id"])

    @staticmethod
    def _safe_error_message(exc: Exception) -> str:
        message = redact(str(exc)).strip()
        return message[:500] or "The agent invocation failed without an error message."

    def run(
        self,
        mission: Mission,
        execution_id: UUID | None = None,
        *,
        run_id: UUID | None = None,
    ) -> AegisState:
        """Start a new execution and persist checkpoints under its stable UUID.

        ``run_id`` is retained as a backwards-compatible alias for callers of the
        original runtime API. It always maps to the persisted ``execution_id``.

        The run pauses at ``await_approval`` before any task executes (status
        becomes ``awaiting_approval``) -- call ``approve_plan``/``reject_plan``
        then ``resume`` to continue.
        """

        if execution_id is not None and run_id is not None and execution_id != run_id:
            raise ValueError("execution_id and run_id must match when both are supplied")
        stable_execution_id = execution_id or run_id or uuid4()
        if self.checkpoints.has_execution(stable_execution_id):
            raise ValueError("Execution already exists; call resume with the same execution_id")

        initial_state = build_initial_state(
            mission, stable_execution_id, event_limit=self.max_state_events
        )
        recent_events = self._record_transition(initial_state, "execution.created", "created")
        initial_state = serialize_state({**initial_state, "recent_events": recent_events})
        return self._execute_graph(stable_execution_id, initial_state)

    def get_state(self, execution_id: UUID) -> AegisState:
        """Read the current checkpointed state without resuming execution --
        the live source of truth for a run's status (ARCHITECTURE.md §6):
        callers needing to display run detail should read this rather than a
        separately-synced Postgres projection."""

        return self._load_state(execution_id)

    def resume(self, execution_id: UUID) -> AegisState:
        """Resume the latest checkpoint without regenerating execution or task IDs."""

        state = self._load_state(execution_id)
        if ExecutionStatus(state["status"]) in _TERMINAL_STATUSES:
            return state

        if ExecutionStatus(state["status"]) != ExecutionStatus.CANCEL_REQUESTED:
            recent_events = self._record_transition(state, "execution.resumed", "running")
            self.graph.update_state(
                self.checkpoints.config(execution_id),
                {"status": ExecutionStatus.RUNNING.value, "recent_events": recent_events},
            )
        return self._execute_graph(execution_id, None)

    def request_cancellation(self, execution_id: UUID) -> AegisState:
        """Persist a cooperative cancellation request before any future task starts."""

        state = self._load_state(execution_id)
        if ExecutionStatus(state["status"]) in _TERMINAL_STATUSES:
            return state
        if ExecutionStatus(state["status"]) == ExecutionStatus.CANCEL_REQUESTED:
            return state

        event = self._new_audit_event(state, "execution.cancellation.requested", "requested")
        recent_events = append_recent_event(state, cast(JsonObject, event.model_dump(mode="json")))
        try:
            self.graph.update_state(
                self.checkpoints.config(execution_id),
                {
                    "status": ExecutionStatus.CANCEL_REQUESTED.value,
                    "recent_events": recent_events,
                },
            )
        except sqlite3.DatabaseError as exc:
            raise CheckpointError("Cancellation request could not be checkpointed") from exc
        self.audit.emit(event)
        return self._load_state(execution_id)

    def approve_plan(self, execution_id: UUID, *, approved_by: str | None = None) -> AegisState:
        """Record plan approval. Does not itself continue execution -- call
        ``resume`` afterward."""

        state = self._require_status(execution_id, ExecutionStatus.AWAITING_APPROVAL)
        approval = dict(state.get("approval") or {})
        approval.update(
            {
                "status": ApprovalStatus.APPROVED.value,
                "decided_by": approved_by,
                "decided_at": serialize_datetime(datetime.now(UTC)),
            }
        )
        event = self._new_audit_event(state, "plan.approved", "approved")
        recent_events = append_recent_event(state, cast(JsonObject, event.model_dump(mode="json")))
        self._checkpoint_update(
            execution_id, {"approval": approval, "recent_events": recent_events}
        )
        self.audit.emit(event)
        return self._load_state(execution_id)

    def reject_plan(
        self, execution_id: UUID, *, reason: str | None = None, rejected_by: str | None = None
    ) -> AegisState:
        """Record plan rejection and fail the execution. Rejection is terminal
        -- there is no automatic replan; start a new mission instead."""

        state = self._require_status(execution_id, ExecutionStatus.AWAITING_APPROVAL)
        approval = dict(state.get("approval") or {})
        approval.update(
            {
                "status": ApprovalStatus.REJECTED.value,
                "decided_by": rejected_by,
                "decided_at": serialize_datetime(datetime.now(UTC)),
                "reason": reason or approval.get("reason"),
            }
        )
        error = build_structured_error(
            "PlanRejected", reason or "The mission plan was rejected during approval."
        )
        event = self._new_audit_event(state, "plan.rejected", "rejected")
        recent_events = append_recent_event(state, cast(JsonObject, event.model_dump(mode="json")))
        self._checkpoint_update(
            execution_id,
            {
                "approval": approval,
                "status": ExecutionStatus.FAILED.value,
                "last_error": error,
                "recent_events": recent_events,
            },
        )
        self.audit.emit(event)
        return self._load_state(execution_id)

    def resolve_escalation(
        self,
        execution_id: UUID,
        *,
        approved: bool,
        resolved_by: str | None = None,
        resolution_reference: str | None = None,
    ) -> AegisState:
        """Resolve a Compliance-triggered escalation. Approving overrides the
        compliance verdict to PASS (recorded as a human override, never
        silently); rejecting fails the execution. Does not itself continue
        execution -- call ``resume`` afterward when approved."""

        state = self._require_status(execution_id, ExecutionStatus.AWAITING_ESCALATION)
        escalation = dict(state.get("escalation") or {})
        decided_at = serialize_datetime(datetime.now(UTC))
        updates: dict[str, Any] = {}

        if approved:
            escalation.update(
                {
                    "status": ApprovalStatus.APPROVED.value,
                    "decided_by": resolved_by,
                    "decided_at": decided_at,
                    "resolution_reference": resolution_reference,
                }
            )
            compliance_data = dict(state.get("compliance_result") or {})
            compliance_data["verdict"] = ComplianceVerdict.PASS.value
            compliance_data["escalation_reference"] = resolution_reference or "human_override"
            updates["compliance_result"] = compliance_data
            event = self._new_audit_event(state, "compliance.escalation.approved", "approved")
        else:
            escalation.update(
                {
                    "status": ApprovalStatus.REJECTED.value,
                    "decided_by": resolved_by,
                    "decided_at": decided_at,
                }
            )
            error = build_structured_error(
                "ComplianceEscalationRejected",
                "The compliance escalation was not approved.",
            )
            updates["status"] = ExecutionStatus.FAILED.value
            updates["last_error"] = error
            event = self._new_audit_event(state, "compliance.escalation.rejected", "rejected")

        updates["escalation"] = escalation
        recent_events = append_recent_event(state, cast(JsonObject, event.model_dump(mode="json")))
        updates["recent_events"] = recent_events
        self._checkpoint_update(execution_id, updates)
        self.audit.emit(event)
        return self._load_state(execution_id)

    def _require_status(self, execution_id: UUID, expected: ExecutionStatus) -> AegisState:
        state = self._load_state(execution_id)
        if ExecutionStatus(state["status"]) != expected:
            raise ValueError(f"Execution is not in status {expected.value!r}")
        return state

    def _checkpoint_update(self, execution_id: UUID, values: dict[str, Any]) -> None:
        try:
            self.graph.update_state(self.checkpoints.config(execution_id), values)
        except sqlite3.DatabaseError as exc:
            raise CheckpointError("Decision could not be checkpointed") from exc


def build_runtime(data_root: Path, checkpoint_path: Path | None = None) -> AegisRuntime:
    return AegisRuntime(data_root=data_root, checkpoint_path=checkpoint_path)
