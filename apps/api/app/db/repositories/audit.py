"""Audit-event repository.

Reads are workspace-scoped through a join to ``missions`` even though
``AuditEventRecord`` carries no foreign key to it (see ``app.models.audit``
for why) — the join is a plain equality condition on the UUID column, so it
still works without a declared relationship or FK constraint.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.audit import AuditEventRecord
from app.models.mission import Mission


class AuditEventRepository(WorkspaceScopedRepository[AuditEventRecord]):
    model = AuditEventRecord

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[AuditEventRecord]]:
        return (
            select(AuditEventRecord)
            .join(Mission, Mission.id == AuditEventRecord.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )

    def search(
        self,
        workspace_id: UUID,
        *,
        run_id: UUID | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEventRecord]:
        statement = self._scoped_select(workspace_id)
        if run_id is not None:
            statement = statement.where(AuditEventRecord.run_id == run_id)
        if event_type is not None:
            statement = statement.where(AuditEventRecord.event_type == event_type)
        statement = (
            statement.order_by(AuditEventRecord.occurred_at.desc()).limit(limit).offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())
