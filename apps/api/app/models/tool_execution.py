"""Tool-call audit tables: generic executions plus the SQL and code-execution
logs called out by name in ARCHITECTURE.md §8, §10."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    JsonObject,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column_type,
    json_column_type,
)


class ToolRiskLevel(StrEnum):
    """Risk tier from the tool-adapter protocol, per ARCHITECTURE.md §10."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolExecutionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


class ToolExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_executions"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(index=True, default=None)
    tool_name: Mapped[str] = mapped_column(String(100))
    tool_version: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[ToolRiskLevel] = mapped_column(
        enum_column_type(ToolRiskLevel, name="tool_risk_level")
    )
    input_sanitized: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
    output_sanitized: Mapped[JsonObject | None] = mapped_column(json_column_type(), default=None)
    status: Mapped[ToolExecutionStatus] = mapped_column(
        enum_column_type(ToolExecutionStatus, name="tool_execution_status"),
        default=ToolExecutionStatus.PENDING,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)


class SqlQuery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Data agent execution log. ``statement`` is always the exact text executed
    against the read-only role — validated ``SELECT``-only before execution by
    the tool adapter (see AGENTS.md), never here.
    """

    __tablename__ = "sql_queries"

    tool_execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tool_executions.id", ondelete="SET NULL"), index=True, default=None
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(index=True, default=None)
    statement: Mapped[str] = mapped_column(Text)
    target_schema: Mapped[str | None] = mapped_column(String(200), default=None)
    row_count: Mapped[int | None] = mapped_column(Integer, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)


class CodeExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Analyst agent sandbox log. ``stdout_redacted``/``stderr_redacted`` are
    already redacted before this row is written, never raw sandbox output.
    """

    __tablename__ = "code_executions"

    tool_execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tool_executions.id", ondelete="SET NULL"), index=True, default=None
    )
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[UUID | None] = mapped_column(index=True, default=None)
    script_hash: Mapped[str] = mapped_column(String(64))
    resource_usage: Mapped[JsonObject | None] = mapped_column(json_column_type(), default=None)
    exit_status: Mapped[int | None] = mapped_column(Integer, default=None)
    stdout_redacted: Mapped[str | None] = mapped_column(Text, default=None)
    stderr_redacted: Mapped[str | None] = mapped_column(Text, default=None)
