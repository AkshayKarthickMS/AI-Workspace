"""Mission routes (ARCHITECTURE.md section 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session, require_workspace_role
from app.models.identity import User, WorkspaceMember, WorkspaceRole
from app.models.mission import Mission as MissionRow
from app.services.missions import create_mission, get_mission, list_missions

router = APIRouter(prefix="/workspaces/{workspace_id}/missions", tags=["missions"])


class MissionCreateRequest(BaseModel):
    raw_request: str = Field(min_length=1, max_length=8000)
    objective: str = Field(min_length=1, max_length=4000)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class MissionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    raw_request: str
    status: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: MissionRow) -> MissionResponse:
        return cls(
            id=row.id,
            workspace_id=row.workspace_id,
            title=row.title,
            raw_request=row.raw_request,
            status=row.status.value,
            created_at=row.created_at,
        )


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission_route(
    workspace_id: UUID,
    body: MissionCreateRequest,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OPERATOR)),
) -> MissionResponse:
    row = create_mission(
        session,
        workspace_id=workspace_id,
        created_by=user.id,
        raw_request=body.raw_request,
        objective=body.objective,
        constraints=body.constraints,
        success_criteria=body.success_criteria,
        context=body.context,
    )
    session.flush()
    return MissionResponse.from_row(row)


@router.get("", response_model=list[MissionResponse])
def list_missions_route(
    workspace_id: UUID,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> list[MissionResponse]:
    rows = list_missions(session, workspace_id=workspace_id)
    return [MissionResponse.from_row(row) for row in rows]


@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission_route(
    workspace_id: UUID,
    mission_id: UUID,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> MissionResponse:
    row = get_mission(session, workspace_id=workspace_id, mission_id=mission_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return MissionResponse.from_row(row)
