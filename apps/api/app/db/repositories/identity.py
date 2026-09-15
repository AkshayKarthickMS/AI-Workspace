"""Identity/RBAC repositories — the workspace-membership root, so these are
plain (unscoped) repositories rather than ``WorkspaceScopedRepository`` (see
``app.db.repositories.base``)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db.repositories.base import Repository
from app.models.identity import User, Workspace, WorkspaceMember


class UserRepository(Repository[User]):
    model = User

    def get_by_identity_subject(self, identity_subject: str) -> User | None:
        statement = select(User).where(User.identity_subject == identity_subject)
        return self.session.execute(statement).scalar_one_or_none()


class WorkspaceRepository(Repository[Workspace]):
    model = Workspace

    def get_by_slug(self, slug: str) -> Workspace | None:
        statement = select(Workspace).where(Workspace.slug == slug)
        return self.session.execute(statement).scalar_one_or_none()

    def list_for_user(self, user_id: UUID) -> list[Workspace]:
        statement = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        return list(self.session.execute(statement).scalars().all())


class WorkspaceMemberRepository(Repository[WorkspaceMember]):
    model = WorkspaceMember

    def get_membership(self, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
        statement = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_for_workspace(self, workspace_id: UUID) -> list[WorkspaceMember]:
        statement = select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        return list(self.session.execute(statement).scalars().all())
