"""QA agent: embedding-based groundedness scoring plus LLM self-critique
defense-in-depth (ARCHITECTURE.md section 7)."""

from __future__ import annotations

from pydantic import BaseModel

from app.agents.qa import QAAgent
from app.events.audit import AuditSink
from app.llm.fake import FakeLLMProvider
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.schemas.agents import Evidence, Finding, Mission

MISSION = Mission(objective="Test QA")


def _no_flags_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
    return response_model()


def test_qa_fails_with_no_findings() -> None:
    agent = QAAgent(
        FakeLLMProvider(factory=_no_flags_factory), FakeEmbeddingProvider(), AuditSink()
    )
    result = agent.invoke(MISSION, run_id=MISSION.mission_id, context={"findings": []})
    assert result.status == "FAIL"
    assert result.corrections


def test_qa_fails_finding_without_evidence() -> None:
    finding = Finding(statement="Revenue grew 10%.", category="fact", confidence=0.9, evidence=[])
    agent = QAAgent(
        FakeLLMProvider(factory=_no_flags_factory), FakeEmbeddingProvider(), AuditSink()
    )
    result = agent.invoke(
        MISSION,
        run_id=MISSION.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )
    assert result.status == "FAIL"
    assert finding.statement in result.unsupported_claims
    assert result.groundedness_scores[str(finding.finding_id)] == 0.0


def test_qa_passes_grounded_finding_when_llm_does_not_flag_it() -> None:
    statement = "Revenue grew 10% year over year."
    evidence = Evidence(source="db", source_type="dataset", excerpt=statement)
    finding = Finding(statement=statement, category="fact", confidence=0.9, evidence=[evidence])
    agent = QAAgent(
        FakeLLMProvider(factory=_no_flags_factory), FakeEmbeddingProvider(), AuditSink()
    )
    result = agent.invoke(
        MISSION,
        run_id=MISSION.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )
    assert result.status == "PASS"
    assert result.groundedness_scores[str(finding.finding_id)] > 0.9


def test_qa_fails_grounded_finding_flagged_by_llm_critique() -> None:
    statement = "Revenue grew 10% year over year."
    evidence = Evidence(source="db", source_type="dataset", excerpt=statement)
    finding = Finding(statement=statement, category="fact", confidence=0.9, evidence=[evidence])

    def flagging_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        return response_model(
            flagged=[{"finding_id": str(finding.finding_id), "reason": "not actually supported"}]
        )

    agent = QAAgent(FakeLLMProvider(factory=flagging_factory), FakeEmbeddingProvider(), AuditSink())
    result = agent.invoke(
        MISSION,
        run_id=MISSION.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )
    assert result.status == "FAIL"
    assert statement in result.unsupported_claims
