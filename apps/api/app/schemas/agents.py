from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.schemas.compliance import ComplianceVerdict


class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    RESEARCH = "research"
    DATA = "data"
    ANALYST = "analyst"
    QA = "qa"
    COMPLIANCE = "compliance"
    REPORT = "report"


class Mission(BaseModel):
    mission_id: UUID = Field(default_factory=uuid4)
    objective: str = Field(min_length=1, max_length=4000)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    agent: AgentRole
    description: str = Field(min_length=1)
    dependencies: list[UUID] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    input: dict[str, Any] = Field(default_factory=dict)
    result_id: UUID | None = None
    error: str | None = None


class Plan(BaseModel):
    plan_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    version: int = Field(default=1, ge=1)
    rationale: str
    tasks: list[Task] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "Plan":
        task_ids = {task.task_id for task in self.tasks}
        for task in self.tasks:
            if any(dependency not in task_ids for dependency in task.dependencies):
                raise ValueError("Task dependency must reference a task in the same plan")
        return self


class Evidence(BaseModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    source: str = Field(min_length=1)
    source_type: Literal["dataset", "document", "url", "user_provided"]
    locator: str | None = None
    excerpt: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class Finding(BaseModel):
    finding_id: UUID = Field(default_factory=uuid4)
    statement: str = Field(min_length=1)
    category: Literal["fact", "trend", "anomaly", "risk", "recommendation"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    metrics: dict[str, float | int | str] = Field(default_factory=dict)


class AgentResult(BaseModel):
    result_id: UUID = Field(default_factory=uuid4)
    agent: AgentRole
    status: Literal["success", "failure"]
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Slide(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=8)


class SlideDeck(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slides: list[Slide] = Field(min_length=1)


class FinalReport(BaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    mission_id: UUID
    title: str
    executive_summary: str
    facts: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    qa_status: Literal["PASS", "FAIL"]
    compliance_verdict: ComplianceVerdict
    slide_deck: SlideDeck | None = None
