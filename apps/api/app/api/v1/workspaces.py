"""Workspace bootstrap routes (ARCHITECTURE.md section 9). Creating a
workspace precedes any membership, so these routes only need identity, not
``require_workspace_role`` -- the creator is granted admin membership as
part of the same transaction (see ``app.services.workspaces``)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session
from app.models.identity import User, Workspace
from app.services.workspaces import SlugConflictError, create_workspace, list_workspaces_for_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    slug: str

    @classmethod
    def from_row(cls, row: Workspace) -> WorkspaceResponse:
        return cls(id=row.id, name=row.name, slug=row.slug)


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace_route(
    body: WorkspaceCreateRequest,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> WorkspaceResponse:
    try:
        workspace = create_workspace(session, name=body.name, owner_user_id=user.id)
    except SlugConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return WorkspaceResponse.from_row(workspace)


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces_route(
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[WorkspaceResponse]:
    return [WorkspaceResponse.from_row(w) for w in list_workspaces_for_user(session, user.id)]
