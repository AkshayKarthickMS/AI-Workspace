"""Approval, escalation, and QA-retry/replan mechanics (ARCHITECTURE.md
section 7; Phase 4 items 22-24). Uses FakeLLMProvider/FakeEmbeddingProvider
throughout -- no CI test may require a live model (AGENTS.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from app.llm.fake import FakeLLMProvider
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.schemas.agents import Evidence, Mission
from app.schemas.planning import DraftPlan, DraftTask
from app.workflows.runtime import AegisRuntime

DATA_ROOT = Path(__file__).parents[3] / "data" / "demo"
DATASET = str(DATA_ROOT / "sales_data.csv")
# Lexically overlaps with ResearchAgent's fixed finding statement ("Approved
# research evidence was retrieved for the mission.") so QA's groundedness
# check passes under FakeEmbeddingProvider, while still containing an email
# address for ComplianceAgent's PII scan to catch.
PII_EXCERPT = (
    "Approved evidence retrieved for the mission: contact jane.doe@example.com "
    "for follow-up."
)


def _llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
    if response_model is DraftPlan:
        return DraftPlan(
            rationale="Test plan",
            tasks=[DraftTask(agent="analyst", description="analyst task")],  # type: ignore[arg-type]
        )
    if response_model.__name__ == "_Critique":
        return response_model()
    raise AssertionError(f"Unexpected response_model requested: {response_model}")


def _build_runtime(**overrides: Any) -> AegisRuntime:
    defaults: dict[str, Any] = {
        "llm": FakeLLMProvider(factory=_llm_factory),
        "embeddings": FakeEmbeddingProvider(),
    }
    defaults.update(overrides)
    return AegisRuntime(DATA_ROOT, **defaults)


def test_resume_before_approval_stays_blocked() -> None:
    mission = Mission(objective="Test", context={"dataset_path": DATASET})
    runtime = _build_runtime()
    state = runtime.run(mission)
    execution_id = UUID(state["execution_id"])

    # No approval recorded yet -- resuming must not let the run slip through.
    state = runtime.resume(execution_id)

    assert state["status"] == "awaiting_approval"
    assert state["approval"]["status"] == "pending"


def test_plan_rejection_fails_the_run() -> None:
    mission = Mission(objective="Test rejection", context={"dataset_path": DATASET})
    runtime = _build_runtime()
    state = runtime.run(mission)
    execution_id = UUID(state["execution_id"])

    runtime.reject_plan(execution_id, reason="not needed", rejected_by="reviewer@example.test")
    state = runtime.resume(execution_id)

    assert state["status"] == "failed"
    assert state["approval"]["status"] == "rejected"
    assert state["last_error"]["error_type"] == "PlanRejected"


def test_approve_plan_raises_when_not_awaiting_approval() -> None:
    mission = Mission(objective="Test", context={"dataset_path": DATASET})
    runtime = _build_runtime()
    state = runtime.run(mission)
    execution_id = UUID(state["execution_id"])
    runtime.approve_plan(execution_id)
    runtime.resume(execution_id)

    with pytest.raises(ValueError):
        runtime.approve_plan(execution_id)


def test_compliance_escalation_can_be_approved_to_complete_the_run() -> None:
    source = Evidence(
        source="https://example.test/contact-info",
        source_type="user_provided",
        excerpt=PII_EXCERPT,
    )
    mission = Mission(objective="Gather contact information for the mission.", context={})

    def llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        if response_model is DraftPlan:
            return DraftPlan(
                rationale="test",
                tasks=[
                    DraftTask(
                        agent="research",  # type: ignore[arg-type]
                        description="find contacts",
                        input={"query": "contact mission evidence"},
                    )
                ],
            )
        if response_model.__name__ == "_Critique":
            return response_model()
        raise AssertionError(f"Unexpected response_model requested: {response_model}")

    runtime = _build_runtime(
        research_sources=[source], llm=FakeLLMProvider(factory=llm_factory)
    )
    state = runtime.run(mission)
    execution_id = UUID(state["execution_id"])
    runtime.approve_plan(execution_id)
    state = runtime.resume(execution_id)

    assert state["status"] == "awaiting_escalation"
    assert state["compliance_result"]["verdict"] == "escalate"
    assert state["escalation"]["status"] == "pending"
    assert state["escalation"]["violations"]

    runtime.resolve_escalation(execution_id, approved=True, resolved_by="reviewer@example.test")
    state = runtime.resume(execution_id)

    assert state["status"] == "completed"
    assert state["compliance_result"]["verdict"] == "pass"
    assert state["compliance_result"]["escalation_reference"] == "human_override"


def test_compliance_escalation_rejection_fails_the_run() -> None:
    source = Evidence(
        source="https://example.test/contact-info",
        source_type="user_provided",
        excerpt=PII_EXCERPT,
    )
    mission = Mission(objective="Gather contact information for the mission.", context={})

    def llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        if response_model is DraftPlan:
            return DraftPlan(
                rationale="test",
                tasks=[
                    DraftTask(
                        agent="research",  # type: ignore[arg-type]
                        description="find contacts",
                        input={"query": "contact mission evidence"},
                    )
                ],
            )
        if response_model.__name__ == "_Critique":
            return response_model()
        raise AssertionError(f"Unexpected response_model requested: {response_model}")

    runtime = _build_runtime(
        research_sources=[source], llm=FakeLLMProvider(factory=llm_factory)
    )
    state = runtime.run(mission)
    execution_id = UUID(state["execution_id"])
    runtime.approve_plan(execution_id)
    state = runtime.resume(execution_id)
    assert state["status"] == "awaiting_escalation"

    runtime.resolve_escalation(execution_id, approved=False, resolved_by="reviewer@example.test")
    state = runtime.resume(execution_id)

    assert state["status"] == "failed"
    assert state["escalation"]["status"] == "rejected"
    assert state["last_error"]["error_type"] == "ComplianceEscalationRejected"


def test_qa_failure_exhausts_retries_and_requires_replan_approval() -> None:
    source = Evidence(
        source="s", source_type="user_provided", excerpt="completely unrelated text with no overlap"
    )
    mission = Mission(objective="Find something", context={})

    def llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        if response_model is DraftPlan:
            return DraftPlan(
                rationale="t",
                tasks=[
                    DraftTask(
                        agent="research",  # type: ignore[arg-type]
                        description="d",
                        input={"query": "find something"},
                    )
                ],
            )
        if response_model.__name__ == "_Critique":
            return response_model()
        raise AssertionError(f"Unexpected response_model requested: {response_model}")

    runtime = _build_runtime(
        research_sources=[source], max_retries=1, llm=FakeLLMProvider(factory=llm_factory)
    )
    state = runtime.run(mission)
    execution_id = UUID(state["execution_id"])
    runtime.approve_plan(execution_id)
    state = runtime.resume(execution_id)

    assert state["status"] == "awaiting_approval"
    assert state["approval"]["reason"] == "qa_failed_after_retries"
    assert state["qa_retry_count"] == 1
