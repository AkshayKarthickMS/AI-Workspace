"""Unit coverage for ReportAgent's LLM-authored narrative synthesis
(AGENTS.md: no CI test may require a live model, so this uses
FakeLLMProvider throughout) and its QA/Compliance gate enforcement."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.agents.report import ReportAgent
from app.llm.fake import FakeLLMProvider
from app.schemas.agents import Finding, Mission

RUN_ID = uuid4()


def _finding(statement: str, category: str = "fact") -> Finding:
    return Finding(statement=statement, category=category, confidence=0.9)  # type: ignore[arg-type]


def _context(**overrides: object) -> dict[str, object]:
    base = {
        "qa_result": {"status": "PASS"},
        "compliance_result": {"verdict": "pass", "rule_set_version": "test"},
        "findings": [],
    }
    base.update(overrides)
    return base


def test_report_raises_when_qa_did_not_pass() -> None:
    agent = ReportAgent(FakeLLMProvider())
    mission = Mission(objective="Test")

    with pytest.raises(ValueError, match="failed QA"):
        agent.run(mission, RUN_ID, None, _context(qa_result={"status": "FAIL"}))


def test_report_raises_when_compliance_did_not_pass() -> None:
    agent = ReportAgent(FakeLLMProvider())
    mission = Mission(objective="Test")

    with pytest.raises(ValueError, match="Compliance clearance"):
        agent.run(
            mission,
            RUN_ID,
            None,
            _context(compliance_result={"verdict": "escalate", "rule_set_version": "test"}),
        )


def test_report_uses_llm_narrative_for_summary_and_recommendations() -> None:
    def factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        assert response_model.__name__ == "_Narrative"
        assert "'North' drives 82% of revenue" in prompt
        return response_model(
            executive_summary="North is the dominant revenue region.",
            recommendations=["Double down on North's go-to-market motion."],
        )

    agent = ReportAgent(FakeLLMProvider(factory=factory))
    mission = Mission(objective="Explain revenue drivers")
    findings = [_finding("'North' drives 82% of revenue", category="driver")]

    report = agent.run(mission, RUN_ID, None, _context(findings=[f.model_dump() for f in findings]))

    assert report.executive_summary == "North is the dominant revenue region."
    assert report.recommendations == ["Double down on North's go-to-market motion."]
    assert report.facts == findings
    assert report.slide_deck is not None
    slide_titles = [slide.title for slide in report.slide_deck.slides]
    assert "Recommendations" in slide_titles


def test_report_tells_llm_when_there_are_no_findings() -> None:
    def factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        assert "none were produced" in prompt
        return response_model(executive_summary="No findings were available.", recommendations=[])

    agent = ReportAgent(FakeLLMProvider(factory=factory))
    mission = Mission(objective="Investigate an empty dataset")

    report = agent.run(mission, RUN_ID, None, _context(findings=[]))

    assert report.executive_summary == "No findings were available."
    assert report.recommendations == []
