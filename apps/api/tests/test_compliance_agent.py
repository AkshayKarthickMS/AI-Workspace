"""Compliance agent: deterministic PII/policy detection (ARCHITECTURE.md
section 7, section 12)."""

from __future__ import annotations

from app.agents.compliance import RULE_SET_VERSION, ComplianceAgent
from app.schemas.agents import Evidence, Finding, Mission
from app.schemas.compliance import ComplianceVerdict

MISSION = Mission(objective="Test Compliance")


def test_compliance_passes_clean_findings() -> None:
    finding = Finding(
        statement="Revenue grew 10% year over year.",
        category="fact",
        confidence=0.9,
        evidence=[Evidence(source="db", source_type="dataset", excerpt="Revenue grew 10%.")],
    )
    agent = ComplianceAgent()
    result = agent.invoke(
        MISSION,
        run_id=MISSION.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )
    assert result.verdict == ComplianceVerdict.PASS
    assert result.violations == []
    assert result.rule_set_version == RULE_SET_VERSION


def test_compliance_escalates_on_email_address() -> None:
    finding = Finding(
        statement="Contact the customer at jane.doe@example.com for follow-up.",
        category="fact",
        confidence=0.9,
        evidence=[],
    )
    agent = ComplianceAgent()
    result = agent.invoke(
        MISSION,
        run_id=MISSION.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )
    assert result.verdict == ComplianceVerdict.ESCALATE
    assert result.violations
    assert result.escalation_reason is not None


def test_compliance_does_not_leak_matched_value_in_violation_text() -> None:
    finding = Finding(
        statement="Contact at jane.doe@example.com.",
        category="fact",
        confidence=0.9,
        evidence=[],
    )
    agent = ComplianceAgent()
    result = agent.invoke(
        MISSION,
        run_id=MISSION.mission_id,
        context={"findings": [finding.model_dump(mode="json")]},
    )
    assert not any("jane.doe@example.com" in violation for violation in result.violations)
