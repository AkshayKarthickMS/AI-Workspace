"""Shared FastAPI dependencies: DB session, identity, and workspace RBAC
(ARCHITECTURE.md section 12; AGENTS.md "authenticate and authorize at every
API boundary").

Identity uses a documented local-development mode only (ARCHITECTURE.md
section 9): a caller-supplied identity subject header, auto-provisioned into
a ``User`` row on first sight. This is explicitly not production
authentication -- it must be replaced by a real identity provider before any
non-dev deployment; nothing here should be mistaken for that.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.repositories import UserRepository, WorkspaceMemberRepository
from app.db.session import session_scope
from app.models.identity import User, WorkspaceMember, WorkspaceRole

_IDENTITY_HEADER = "X-Aegis-Identity-Subject"
_DISPLAY_NAME_HEADER = "X-Aegis-Display-Name"

_ROLE_RANK: dict[WorkspaceRole, int] = {
    WorkspaceRole.VIEWER: 0,
    WorkspaceRole.REVIEWER: 1,
    WorkspaceRole.OPERATOR: 2,
    WorkspaceRole.ADMIN: 3,
}


def get_db_session() -> Iterator[Session]:
    """Request-scoped, transactional session: commits after a successful
    response, rolls back on any exception (see ``app.db.session.session_scope``).
    """

    with session_scope() as session:
        yield session


def get_current_user(
    session: Session = Depends(get_db_session),
    identity_subject: str | None = Header(default=None, alias=_IDENTITY_HEADER),
    display_name: str | None = Header(default=None, alias=_DISPLAY_NAME_HEADER),
) -> User:
    if not identity_subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {_IDENTITY_HEADER} header (local development identity mode).",
        )
    users = UserRepository(session)
    user = users.get_by_identity_subject(identity_subject)
    if user is None:
        try:
            with session.begin_nested():
                user = users.add(
                    User(
                        identity_subject=identity_subject,
                        display_name=display_name or identity_subject,
                    )
                )
        except IntegrityError:
            # Lost a race with a concurrent request auto-provisioning the same
            # identity (the browser routinely fires several requests at once)
            # -- the SAVEPOINT above rolled back our insert, so the other
            # request's committed row is now visible; just read it.
            user = users.get_by_identity_subject(identity_subject)
            if user is None:
                raise
    return user


def require_workspace_role(
    minimum: WorkspaceRole,
) -> Callable[[UUID, Session, User], WorkspaceMember]:
    """Build a dependency enforcing the current user holds at least
    ``minimum`` role in the ``workspace_id`` path parameter's workspace.

    A missing membership returns 404, not 403, so a non-member can't
    distinguish "no access" from "doesn't exist" (AGENTS.md - least
    information disclosure at the API boundary).
    """

    def dependency(
        workspace_id: UUID,
        session: Session = Depends(get_db_session),
        user: User = Depends(get_current_user),
    ) -> WorkspaceMember:
        membership = WorkspaceMemberRepository(session).get_membership(workspace_id, user.id)
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        if _ROLE_RANK[membership.role] < _ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least the {minimum.value!r} role in this workspace.",
            )
        return membership

    return dependency
