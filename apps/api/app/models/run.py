"""Run and run-checkpoint tables (ARCHITECTURE.md §8)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    JsonObject,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column_type,
    json_column_type,
)


class RunStatus(StrEnum):
    """Mirrors the string values of ``app.workflows.state.ExecutionStatus``.

    Defined independently rather than imported: the persistence layer must not
    depend on the workflow/business-logic layer. Comparisons and persistence
    use the shared string values, not Python identity, so this stays in sync
    by convention — keep both enums' values identical when either changes.
    """

    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_ESCALATION = "awaiting_escalation"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class Run(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """``id`` is normally the LangGraph ``execution_id`` (thread id) so a run row
    and its checkpointed graph state share one identifier.
    """

    __tablename__ = "runs"

    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), index=True
    )
    # Nullable: the runtime graph plans (an LLM call) as the first step of a
    # run rather than before it, so a just-created Run has no plan yet. The
    # background run handler backfills this once planning completes.
    plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mission_plans.id", ondelete="SET NULL"), index=True, default=None
    )
    graph_version: Mapped[str] = mapped_column(String(50), default="1")
    status: Mapped[RunStatus] = mapped_column(
        enum_column_type(RunStatus, name="run_status"), default=RunStatus.RUNNING
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_summary: Mapped[str | None] = mapped_column(Text, default=None)


class RunCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable, queryable mirror of the LangGraph checkpoint already persisted
    locally by ``RuntimeCheckpointStore`` (SQLite) — see ARCHITECTURE.md §15
    item 1 for the eventual Postgres-backed checkpointer this schema supports.
    """

    __tablename__ = "run_checkpoints"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_run_checkpoint_sequence"),)

    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    node_name: Mapped[str] = mapped_column(String(100))
    state_payload: Mapped[JsonObject] = mapped_column(json_column_type())
