"""Versioned, JSON-only state contracts for the LangGraph runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self, TypedDict, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.agents import AgentResult, FinalReport, Mission, Plan, Task
from app.schemas.compliance import ComplianceReviewResult
from app.schemas.qa import QAResult

STATE_SCHEMA_VERSION: Literal[3] = 3
MAX_STATE_EVENT_LIMIT = 100

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_ESCALATION = "awaiting_escalation"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StructuredError(BaseModel):
    """Safe, serializable failure metadata retained with an execution."""

    model_config = ConfigDict(extra="forbid")

    error_type: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    timestamp: str = Field(min_length=1, max_length=40)
    task_id: UUID | None = None
    agent: str | None = Field(default=None, max_length=100)


class ApprovalRecord(BaseModel):
    """Pre-execution plan approval gate (ARCHITECTURE.md section 2, section 7).

    Also reused for the post-QA-retry "replan" gate -- same shape, same
    ``await_approval`` node, distinguished only by ``reason``.
    """

    model_config = ConfigDict(extra="forbid")

    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str | None = Field(default=None, max_length=500)
    requested_at: str | None = Field(default=None, max_length=40)
    decided_at: str | None = Field(default=None, max_length=40)
    decided_by: str | None = Field(default=None, max_length=200)


class EscalationRecord(BaseModel):
    """Compliance-triggered mid-run escalation gate (ARCHITECTURE.md section 7,
    section 12)."""

    model_config = ConfigDict(extra="forbid")

    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str | None = Field(default=None, max_length=500)
    violations: list[str] = Field(default_factory=list)
    requested_at: str | None = Field(default=None, max_length=40)
    decided_at: str | None = Field(default=None, max_length=40)
    decided_by: str | None = Field(default=None, max_length=200)
    resolution_reference: str | None = Field(default=None, max_length=200)


class RuntimeStateRecord(BaseModel):
    """Validation boundary for persisted LangGraph state.

    UUID and datetime fields are validated as domain values here, then emitted as
    canonical JSON primitives by ``model_dump(mode="json")`` before entering the graph.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[3] = STATE_SCHEMA_VERSION
    mission_id: UUID
    execution_id: UUID
    mission: JsonObject
    plan: JsonObject | None = None
    tasks: dict[str, JsonObject] = Field(default_factory=dict)
    current_task_id: UUID | None = None
    results: dict[str, JsonObject] = Field(default_factory=dict)
    qa_result: JsonObject | None = None
    qa_retry_count: int = Field(default=0, ge=0)
    compliance_result: JsonObject | None = None
    approval: JsonObject | None = None
    escalation: JsonObject | None = None
    final_report: JsonObject | None = None
    retry_counts: dict[str, int] = Field(default_factory=dict)
    agent_statuses: dict[str, AgentExecutionStatus] = Field(default_factory=dict)
    task_errors: dict[str, StructuredError] = Field(default_factory=dict)
    last_error: StructuredError | None = None
    event_limit: int = Field(default=25, ge=1, le=MAX_STATE_EVENT_LIMIT)
    recent_events: list[JsonObject] = Field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.RUNNING

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        mission = Mission.model_validate(self.mission)
        if mission.mission_id != self.mission_id:
            raise ValueError("State mission_id must match the serialized mission")
        if len(self.recent_events) > self.event_limit:
            raise ValueError("State recent_events exceeds the configured event limit")

        task_ids: set[str] = set()
        for task_id, task_data in self.tasks.items():
            task = Task.model_validate(task_data)
            if str(task.task_id) != task_id:
                raise ValueError("Task map keys must match serialized task IDs")
            task_ids.add(task_id)

        if self.plan is not None:
            plan = Plan.model_validate(self.plan)
            if plan.mission_id != self.mission_id:
                raise ValueError("State plan must belong to the serialized mission")
            if {str(task.task_id) for task in plan.tasks} != task_ids:
                raise ValueError("State tasks must match the serialized plan")

        if self.current_task_id is not None and str(self.current_task_id) not in task_ids:
            raise ValueError("State current_task_id must reference a task")
        if not set(self.retry_counts).issubset(task_ids):
            raise ValueError("State retry counts must reference known tasks")
        if not set(self.agent_statuses).issubset(task_ids):
            raise ValueError("State agent statuses must reference known tasks")
        if not set(self.task_errors).issubset(task_ids):
            raise ValueError("State task errors must reference known tasks")

        for result_id, result_data in self.results.items():
            result = AgentResult.model_validate(result_data)
            if str(result.result_id) != result_id:
                raise ValueError("Result map keys must match serialized result IDs")
        if self.qa_result is not None:
            QAResult.model_validate(self.qa_result)
        if self.compliance_result is not None:
            ComplianceReviewResult.model_validate(self.compliance_result)
        if self.approval is not None:
            ApprovalRecord.model_validate(self.approval)
        if self.escalation is not None:
            EscalationRecord.model_validate(self.escalation)
        if self.final_report is not None:
            report = FinalReport.model_validate(self.final_report)
            if report.mission_id != self.mission_id:
                raise ValueError("Final report must belong to the serialized mission")
        return self


class AegisState(TypedDict, total=False):
    """JSON-only graph state. Runtime services and Pydantic objects stay outside it."""

    schema_version: int
    mission_id: str
    execution_id: str
    mission: JsonObject
    plan: JsonObject | None
    tasks: dict[str, JsonObject]
    current_task_id: str | None
    results: dict[str, JsonObject]
    qa_result: JsonObject | None
    qa_retry_count: int
    compliance_result: JsonObject | None
    approval: JsonObject | None
    escalation: JsonObject | None
    final_report: JsonObject | None
    retry_counts: dict[str, int]
    agent_statuses: dict[str, str]
    task_errors: dict[str, JsonObject]
    last_error: JsonObject | None
    event_limit: int
    recent_events: list[JsonObject]
    status: str


class StateVersionError(ValueError):
    """Raised when checkpointed state belongs to an unsupported schema version."""


def serialize_datetime(value: datetime) -> str:
    """Render a timezone-aware datetime in canonical UTC RFC 3339 form."""

    if value.tzinfo is None:
        raise ValueError("Datetime values in runtime state must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def build_structured_error(
    error_type: str,
    message: str,
    *,
    task_id: UUID | None = None,
    agent: str | None = None,
    timestamp: datetime | None = None,
) -> JsonObject:
    error = StructuredError(
        error_type=error_type,
        message=message,
        timestamp=serialize_datetime(timestamp or datetime.now(UTC)),
        task_id=task_id,
        agent=agent,
    )
    return cast(JsonObject, error.model_dump(mode="json"))


def _migrate_v2_to_v3(payload: dict[str, object]) -> dict[str, object]:
    """Upgrade a schema-2 (Phase 3) checkpoint payload for schema-3 code.

    Schema 2 had no approval/escalation gates or QA-retry bookkeeping; an
    in-flight v2 execution resumed under Phase 4 code simply has none of that
    history yet, so the new fields start at their empty defaults.
    """

    migrated = dict(payload)
    migrated.setdefault("qa_retry_count", 0)
    migrated.setdefault("approval", None)
    migrated.setdefault("escalation", None)
    migrated["schema_version"] = 3
    return migrated


_MIGRATIONS: dict[int, Callable[[dict[str, object]], dict[str, object]]] = {
    2: _migrate_v2_to_v3,
}


def serialize_state(state: Mapping[str, object]) -> AegisState:
    """Validate runtime state and return its canonical JSON-only representation.

    Transparently upgrades an older, still-migratable ``schema_version`` first
    (see ``_MIGRATIONS``) so an in-flight checkpoint from a prior schema keeps
    working rather than being rejected outright.
    """

    payload: dict[str, object] = dict(state)
    version = payload.get("schema_version")
    while isinstance(version, int) and version in _MIGRATIONS:
        payload = _MIGRATIONS[version](payload)
        version = payload.get("schema_version")

    try:
        record = RuntimeStateRecord.model_validate(payload)
    except ValueError as exc:
        if isinstance(version, int) and version != STATE_SCHEMA_VERSION:
            raise StateVersionError("Unsupported runtime state schema version") from exc
        raise
    return cast(AegisState, record.model_dump(mode="json"))


def deserialize_state(payload: Mapping[str, object]) -> AegisState:
    """Validate a persisted JSON payload before resuming it in LangGraph."""

    return serialize_state(payload)


def build_initial_state(
    mission: Mission, execution_id: UUID, *, event_limit: int
) -> AegisState:
    """Create a validated graph state without placing Pydantic objects in the graph."""

    return serialize_state(
        {
            "schema_version": STATE_SCHEMA_VERSION,
            "mission_id": mission.mission_id,
            "execution_id": execution_id,
            "mission": mission.model_dump(mode="json"),
            "event_limit": event_limit,
        }
    )


def append_recent_event(state: AegisState, event: JsonObject) -> list[JsonObject]:
    """Keep only the configured recent-event window in graph state."""

    event_limit = int(state["event_limit"])
    return [*state.get("recent_events", []), event][-event_limit:]
