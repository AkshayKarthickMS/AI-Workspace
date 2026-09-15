"""Workspace bootstrap use cases (ARCHITECTURE.md section 6). Workspace
creation itself precedes any RBAC check -- there is no membership to check
yet -- so it lives outside the ``require_workspace_role`` dependency chain;
the creator is granted admin membership as part of the same transaction."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.repositories import WorkspaceMemberRepository, WorkspaceRepository
from app.models.identity import Workspace, WorkspaceMember, WorkspaceRole

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class SlugConflictError(ValueError):
    """Raised when the requested (or derived) workspace slug is already taken."""


def slugify(name: str) -> str:
    slug = _SLUG_PATTERN.sub("-", name.strip().lower()).strip("-")
    return slug or "workspace"


def create_workspace(session: Session, *, name: str, owner_user_id: UUID) -> Workspace:
    repo = WorkspaceRepository(session)
    slug = slugify(name)
    if repo.get_by_slug(slug) is not None:
        raise SlugConflictError(f"Workspace slug {slug!r} is already in use")

    workspace = repo.add(Workspace(name=name, slug=slug))
    WorkspaceMemberRepository(session).add(
        WorkspaceMember(workspace_id=workspace.id, user_id=owner_user_id, role=WorkspaceRole.ADMIN)
    )
    return workspace


def list_workspaces_for_user(session: Session, user_id: UUID) -> list[Workspace]:
    return WorkspaceRepository(session).list_for_user(user_id)
