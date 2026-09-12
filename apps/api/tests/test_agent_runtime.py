from pathlib import Path

from app.agents.orchestrator import OrchestratorAgent
from app.agents.verification import VerificationAgent
from app.events.audit import AuditSink
from app.schemas.agents import AgentRole, Evidence, Finding, Mission
from app.tools.data_analysis import PandasSalesAnalysisTool
from app.workflows.runtime import AegisRuntime

DATA_ROOT = Path(__file__).parents[3] / "data" / "demo"
DATASET = str(DATA_ROOT / "sales_data.csv")


def test_plan_creation_and_task_routing() -> None:
    mission = Mission(
        objective="Analyze sales performance and produce an executive summary.",
        context={"dataset_path": DATASET},
    )
    plan = OrchestratorAgent(AuditSink()).invoke(mission, run_id=mission.mission_id)

    roles = [task.agent for task in plan.tasks]
    assert roles == [
        AgentRole.RESEARCH,
        AgentRole.DATA_ANALYST,
        AgentRole.VERIFICATION,
        AgentRole.REPORT,
    ]
    assert plan.tasks[2].dependencies == [plan.tasks[0].task_id, plan.tasks[1].task_id]
    assert plan.tasks[3].dependencies == [plan.tasks[2].task_id]


def test_runtime_transitions_to_verified_report() -> None:
    source = Evidence(
        source="https://example.test/approved-brief",
        source_type="url",
        locator="/approved-brief",
        excerpt="Approved context for the sales mission.",
    )
    mission = Mission(
        objective="Analyze sales performance and produce an executive summary.",
        context={"dataset_path": DATASET},
    )
    runtime = AegisRuntime(DATA_ROOT, research_sources=[source])
    state = runtime.run(mission)

    assert state["status"] == "completed"
    assert state["verification"].status == "PASS"
    assert state["final_report"].verification_status == "PASS"
    assert {event.actor for event in state["audit_events"]} >= {
        "orchestrator",
        "research",
        "data_analyst",
        "verification",
        "report",
    }


def test_verification_rejects_unsupported_claims() -> None:
    mission = Mission(objective="Verify a claim")
    finding = Finding(statement="Unsupported claim", category="fact", confidence=0.5)
    result = VerificationAgent(AuditSink()).invoke(
        mission,
        run_id=mission.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )

    assert result.status == "FAIL"
    assert result.unsupported_claims == ["Unsupported claim"]
    assert result.corrections


def test_failure_is_retried_then_recorded() -> None:
    mission = Mission(
        objective="Analyze a missing dataset.",
        context={"dataset_path": str(DATA_ROOT / "missing.csv")},
    )
    runtime = AegisRuntime(DATA_ROOT, max_retries=1)
    state = runtime.run(mission)

    assert state["status"] == "failed"
    assert state["errors"]
    assert any(
        event.status == "failed" and event.actor == "data_analyst"
        for event in state["audit_events"]
    )


def test_data_tool_rejects_paths_outside_allowed_root() -> None:
    tool = PandasSalesAnalysisTool(DATA_ROOT)
    try:
        tool.analyze(str(DATA_ROOT.parent / "sales_data.csv"))
    except ValueError as exc:
        assert "outside the allowed data root" in str(exc)
    else:
        raise AssertionError("Expected an out-of-root dataset path to be rejected")
