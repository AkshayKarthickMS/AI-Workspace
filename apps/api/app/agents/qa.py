from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.llm.base import LLMProvider
from app.retrieval.embeddings import EmbeddingProvider, cosine_similarity
from app.schemas.agents import AgentRole, Finding, Mission
from app.schemas.qa import QAResult

_GROUNDEDNESS_THRESHOLD = 0.35

_CRITIQUE_SYSTEM_PROMPT = (
    "You are a skeptical fact-checker reviewing an AI agent's findings. For each "
    "claim and its attached evidence excerpts, flag the claim ONLY if the evidence "
    "does not actually support it. Do not flag claims that are well supported. "
    "Reply with JSON only."
)


class _CritiqueFlag(BaseModel):
    finding_id: str
    reason: str = Field(max_length=300)


class _Critique(BaseModel):
    flagged: list[_CritiqueFlag] = Field(default_factory=list)


class QAAgent(BaseAgent[QAResult]):
    """Evidentiary support plus groundedness/hallucination checks
    (ARCHITECTURE.md section 7). Supersedes VerificationAgent: findings must
    now be both evidence-backed AND semantically grounded in that evidence,
    checked two ways -- embedding similarity (deterministic, cheap, always
    run) and an LLM self-critique pass (defense in depth)."""

    role = AgentRole.QA

    def __init__(
        self, llm: LLMProvider, embeddings: EmbeddingProvider, audit: AuditSink | None = None
    ) -> None:
        super().__init__(audit)
        self.llm = llm
        self.embeddings = embeddings

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> QAResult:
        findings = [Finding.model_validate(item) for item in context.get("findings", [])]
        if not findings:
            return QAResult(
                status="FAIL",
                corrections=["No findings were produced; collect evidence before reporting."],
            )

        unsupported: list[str] = []
        groundedness_scores: dict[str, float] = {}
        for finding in findings:
            score = self._groundedness_score(finding)
            groundedness_scores[str(finding.finding_id)] = round(score, 4)
            if not finding.evidence or score < _GROUNDEDNESS_THRESHOLD:
                unsupported.append(finding.statement)

        flagged_ids = self._llm_critique(findings, run_id=run_id, task_id=task_id)
        for finding in findings:
            if str(finding.finding_id) in flagged_ids and finding.statement not in unsupported:
                unsupported.append(finding.statement)

        corrections: list[str] = []
        if unsupported:
            corrections.append("Remove or better source every claim without grounded evidence.")

        status: Literal["PASS", "FAIL"] = "FAIL" if unsupported else "PASS"
        evidence = [item for finding in findings for item in finding.evidence]
        return QAResult(
            status=status,
            checked_findings=[finding.finding_id for finding in findings],
            unsupported_claims=unsupported,
            groundedness_scores=groundedness_scores,
            corrections=corrections,
            evidence=evidence,
        )

    def _groundedness_score(self, finding: Finding) -> float:
        excerpts = [evidence.excerpt for evidence in finding.evidence if evidence.excerpt]
        if not excerpts:
            return 0.0
        vectors = self.embeddings.embed([finding.statement, *excerpts])
        claim_vector, evidence_vectors = vectors[0], vectors[1:]
        return max(cosine_similarity(claim_vector, vector) for vector in evidence_vectors)

    def _llm_critique(
        self, findings: list[Finding], *, run_id: UUID, task_id: UUID | None
    ) -> set[str]:
        prompt_lines = [
            f"- id={finding.finding_id} claim={finding.statement!r} "
            f"evidence={[e.excerpt for e in finding.evidence if e.excerpt]!r}"
            for finding in findings
        ]
        critique = self.llm.complete(
            system=_CRITIQUE_SYSTEM_PROMPT,
            prompt="\n".join(prompt_lines),
            response_model=_Critique,
            run_id=run_id,
            task_id=task_id,
        )
        return {flag.finding_id for flag in critique.flagged}
