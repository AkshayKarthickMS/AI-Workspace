"""Append-only audit trail (ARCHITECTURE.md §8, §11).

``mission_id``/``run_id``/``task_id`` are intentionally plain indexed UUID
columns, not foreign keys: an audit write must never fail because the mission
or run it references hasn't been persisted yet (or, for ad-hoc/test runs,
never will be). The audit trail's job is to record what happened, not to
enforce referential integrity against other tables.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import JsonObject, UUIDPrimaryKeyMixin, json_column_type


class AuditEventRecord(UUIDPrimaryKeyMixin):
    __tablename__ = "audit_events"

    event_type: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(100))
    mission_id: Mapped[UUID] = mapped_column(index=True)
    run_id: Mapped[UUID] = mapped_column(index=True)
    task_id: Mapped[UUID | None] = mapped_column(index=True, default=None)
    status: Mapped[str] = mapped_column(String(50))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    event_metadata: Mapped[JsonObject] = mapped_column(json_column_type(), default=dict)
