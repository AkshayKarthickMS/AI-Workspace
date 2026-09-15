"""Identity and workspace-scoped RBAC tables (ARCHITECTURE.md §8, §12)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column_type


class WorkspaceRole(StrEnum):
    """Workspace-scoped RBAC role, per ARCHITECTURE.md §12."""

    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A person known to AegisOS. Workspace permissions live on ``WorkspaceMember``;
    ``role`` here is a coarse system-level role (e.g. standard vs. platform admin),
    not the per-workspace RBAC role.
    """

    __tablename__ = "users"

    identity_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50), default="member")


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ownership boundary for missions, runs, and the knowledge base."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's RBAC role within one workspace."""

    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[WorkspaceRole] = mapped_column(
        enum_column_type(WorkspaceRole, name="workspace_role"), default=WorkspaceRole.VIEWER
    )
