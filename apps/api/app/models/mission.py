"""Mission intake, plan, and plan-step tables (ARCHITECTURE.md §8)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    JsonObject,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column_type,
    json_column_type,
)
from app.schemas.agents import AgentRole, TaskStatus


class MissionStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Mission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "missions"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    raw_request: Mapped[str] = mapped_column(Text)
    normalized_request: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
    status: Mapped[MissionStatus] = mapped_column(
        enum_column_type(MissionStatus, name="mission_status"), default=MissionStatus.DRAFT
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))


class MissionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mission_plans"
    __table_args__ = (UniqueConstraint("mission_id", "version", name="uq_mission_plan_version"),)

    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    plan: Mapped[JsonObject] = mapped_column(json_column_type())
    status: Mapped[PlanStatus] = mapped_column(
        enum_column_type(PlanStatus, name="plan_status"), default=PlanStatus.DRAFT
    )
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), default=None)


class PlanStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One task within a plan. ``id`` is normally the domain ``Task.task_id`` the
    LangGraph runtime already generated, passed explicitly by the repository
    caller rather than left to the default, so a run's checkpointed tasks and
    their persisted rows share one identifier.
    """

    __tablename__ = "plan_steps"

    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("mission_plans.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    agent_role: Mapped[AgentRole] = mapped_column(enum_column_type(AgentRole, name="agent_role"))
    description: Mapped[str] = mapped_column(Text)
    dependencies: Mapped[list[str]] = mapped_column(json_column_type(), default=list)
    input: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
    acceptance_criteria: Mapped[list[str]] = mapped_column(json_column_type(), default=list)
    status: Mapped[TaskStatus] = mapped_column(
        enum_column_type(TaskStatus, name="task_status"), default=TaskStatus.PENDING
    )
    result_id: Mapped[UUID | None] = mapped_column(default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
