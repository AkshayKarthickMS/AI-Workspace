import re
from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.schemas.agents import AgentRole, Finding, Mission
from app.schemas.compliance import ComplianceReviewResult, ComplianceVerdict

RULE_SET_VERSION = "2026.1"

# Detects the *shape* of sensitive data, never logs the matched value itself
# (AGENTS.md: redact before logs, events, audit payloads, and artifacts).
_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email address": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "ssn-like number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit-card-like number": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "phone number": re.compile(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"),
}


class ComplianceAgent(BaseAgent[ComplianceReviewResult]):
    """Policy/PII/regulatory review gate (ARCHITECTURE.md section 7, section 12).

    Deterministic and rule-based by design, unlike QA's LLM-assisted checks:
    a compliance verdict must be reproducible from the same inputs every
    time, which is the whole point of a compliance gate.
    """

    role = AgentRole.COMPLIANCE

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> ComplianceReviewResult:
        findings = [Finding.model_validate(item) for item in context.get("findings", [])]

        violations: list[str] = []
        for finding in findings:
            texts = [finding.statement, *(evidence.excerpt or "" for evidence in finding.evidence)]
            for text in texts:
                for label, pattern in _PII_PATTERNS.items():
                    if pattern.search(text):
                        violations.append(f"Possible {label} in finding {finding.finding_id}")

        verdict = ComplianceVerdict.ESCALATE if violations else ComplianceVerdict.PASS
        return ComplianceReviewResult(
            rule_set_version=RULE_SET_VERSION,
            verdict=verdict,
            reviewed_finding_ids=[finding.finding_id for finding in findings],
            violations=violations,
            escalation_reason=(
                "Potential sensitive data detected; human review required." if violations else None
            ),
        )
