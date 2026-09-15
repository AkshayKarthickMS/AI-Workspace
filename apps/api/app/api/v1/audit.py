"""Filterable audit search route (ARCHITECTURE.md section 9, section 11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_workspace_role
from app.db.repositories import AuditEventRepository
from app.models.audit import AuditEventRecord
from app.models.identity import WorkspaceMember, WorkspaceRole

router = APIRouter(prefix="/workspaces/{workspace_id}/audit-events", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: UUID
    event_type: str
    actor: str
    mission_id: UUID
    run_id: UUID
    task_id: UUID | None
    status: str
    occurred_at: datetime
    metadata: dict[str, Any]

    @classmethod
    def from_row(cls, row: AuditEventRecord) -> AuditEventResponse:
        return cls(
            id=row.id,
            event_type=row.event_type,
            actor=row.actor,
            mission_id=row.mission_id,
            run_id=row.run_id,
            task_id=row.task_id,
            status=row.status,
            occurred_at=row.occurred_at,
            metadata=row.event_metadata,
        )


@router.get("", response_model=list[AuditEventResponse])
def search_audit_events_route(
    workspace_id: UUID,
    run_id: UUID | None = None,
    event_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> list[AuditEventResponse]:
    rows = AuditEventRepository(session).search(
        workspace_id, run_id=run_id, event_type=event_type, limit=limit, offset=offset
    )
    return [AuditEventResponse.from_row(row) for row in rows]
