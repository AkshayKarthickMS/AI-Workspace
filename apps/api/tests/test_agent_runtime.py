"""End-to-end and orchestrator-level tests for the LangGraph runtime.

Uses FakeLLMProvider/FakeEmbeddingProvider throughout (AGENTS.md: no CI test
may require a downloaded model or a live network call).
"""

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.agents.orchestrator import OrchestratorAgent
from app.events.audit import AuditSink
from app.llm.fake import FakeLLMProvider
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.schemas.agents import AgentRole, Mission
from app.schemas.planning import DraftPlan, DraftTask
from app.tools.tabular_analysis import GenericTabularAnalysisTool
from app.workflows.runtime import AegisRuntime

DATA_ROOT = Path(__file__).parents[3] / "data" / "demo"
DATASET = str(DATA_ROOT / "sales_data.csv")


def _approve_and_resume(runtime: AegisRuntime, state: dict[str, Any]) -> dict[str, Any]:
    """Every run now pauses at await_approval before any task executes
    (ARCHITECTURE.md section 2/7) -- approve it once to let a happy-path test
    proceed to completion."""

    assert state["status"] == "awaiting_approval"
    execution_id = UUID(state["execution_id"])
    runtime.approve_plan(execution_id)
    return runtime.resume(execution_id)


def _draft_plan(*agents: str) -> DraftPlan:
    return DraftPlan(
        rationale="Test plan",
        tasks=[DraftTask(agent=agent, description=f"{agent} task") for agent in agents],  # type: ignore[arg-type]
    )


def _llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
    if response_model is DraftPlan:
        return _draft_plan("analyst")
    if response_model.__name__ == "_Critique":
        return response_model()
    raise AssertionError(f"Unexpected response_model requested: {response_model}")


def test_plan_creation_and_task_routing() -> None:
    mission = Mission(
        objective="Analyze sales performance and produce an executive summary.",
        context={"dataset_path": DATASET},
    )
    llm = FakeLLMProvider(responses=[_draft_plan("research", "analyst")])
    plan = OrchestratorAgent(llm, AuditSink()).invoke(mission, run_id=mission.mission_id)

    roles = [task.agent for task in plan.tasks]
    assert roles == [
        AgentRole.RESEARCH,
        AgentRole.ANALYST,
        AgentRole.QA,
        AgentRole.COMPLIANCE,
        AgentRole.REPORT,
    ]
    assert plan.tasks[2].dependencies == [plan.tasks[0].task_id, plan.tasks[1].task_id]
    assert plan.tasks[3].dependencies == [plan.tasks[2].task_id]
    assert plan.tasks[4].dependencies == [plan.tasks[3].task_id]


def test_orchestrator_deduplicates_repeated_agent_choices() -> None:
    mission = Mission(objective="Repeat test", context={"dataset_path": DATASET})
    llm = FakeLLMProvider(
        responses=[
            DraftPlan(
                rationale="dup",
                tasks=[
                    DraftTask(agent="analyst", description="first"),  # type: ignore[arg-type]
                    DraftTask(agent="analyst", description="second"),  # type: ignore[arg-type]
                ],
            )
        ]
    )
    plan = OrchestratorAgent(llm, AuditSink()).invoke(mission, run_id=mission.mission_id)
    gathering = [task for task in plan.tasks if task.agent == AgentRole.ANALYST]
    assert len(gathering) == 1


def test_runtime_transitions_to_delivered_report() -> None:
    mission = Mission(
        objective="Analyze sales performance and produce an executive summary.",
        context={"dataset_path": DATASET},
    )
    runtime = AegisRuntime(
        DATA_ROOT,
        llm=FakeLLMProvider(factory=_llm_factory),
        embeddings=FakeEmbeddingProvider(),
    )
    state = runtime.run(mission)
    state = _approve_and_resume(runtime, state)

    assert state["status"] == "completed"
    assert state["approval"] is not None
    assert state["approval"]["status"] == "approved"
    assert state["qa_result"] is not None
    assert state["qa_result"]["status"] == "PASS"
    assert state["compliance_result"] is not None
    assert state["compliance_result"]["verdict"] == "pass"
    final_report = state["final_report"]
    assert final_report is not None
    assert final_report["qa_status"] == "PASS"
    assert final_report["compliance_verdict"] == "pass"
    assert final_report["slide_deck"] is not None
    assert {event.actor for event in runtime.audit.events} >= {
        "orchestrator",
        "analyst",
        "qa",
        "compliance",
        "report",
    }


def test_failure_is_retried_then_recorded() -> None:
    mission = Mission(
        objective="Analyze a missing dataset.",
        context={"dataset_path": str(DATA_ROOT / "missing.csv")},
    )
    runtime = AegisRuntime(
        DATA_ROOT,
        max_retries=1,
        llm=FakeLLMProvider(factory=_llm_factory),
        embeddings=FakeEmbeddingProvider(),
    )
    state = runtime.run(mission)
    state = _approve_and_resume(runtime, state)

    assert state["status"] == "failed"
    assert state["last_error"]
    assert state["task_errors"]
    assert any(
        event.status == "failed" and event.actor == "analyst" for event in runtime.audit.events
    )


def test_data_tool_rejects_paths_outside_allowed_root() -> None:
    tool = GenericTabularAnalysisTool(DATA_ROOT)
    try:
        tool.analyze(str(DATA_ROOT.parent / "sales_data.csv"))
    except ValueError as exc:
        assert "outside the allowed data root" in str(exc)
    else:
        raise AssertionError("Expected an out-of-root dataset path to be rejected")
