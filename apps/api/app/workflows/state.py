from typing import Literal, TypedDict
from uuid import UUID

from app.events.audit import AuditEvent
from app.schemas.agents import (
    AgentResult,
    FinalReport,
    Mission,
    Plan,
    Task,
    VerificationResult,
)


class AegisState(TypedDict, total=False):
    """Explicit, bounded LangGraph state for one mission run."""

    mission: Mission
    run_id: UUID
    plan: Plan
    tasks: dict[UUID, Task]
    current_task_id: UUID | None
    results: dict[UUID, AgentResult]
    verification: VerificationResult | None
    final_report: FinalReport | None
    audit_events: list[AuditEvent]
    retry_counts: dict[UUID, int]
    status: Literal["planned", "running", "completed", "failed"]
    errors: list[str]
