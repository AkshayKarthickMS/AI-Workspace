"""Generic repository bases shared by every table's repository (ARCHITECTURE.md
section 6)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.base import UUIDPrimaryKeyMixin


class _SessionBoundRepository[ModelT: UUIDPrimaryKeyMixin]:
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.session.flush()


class Repository[ModelT: UUIDPrimaryKeyMixin](_SessionBoundRepository[ModelT]):
    """Unscoped CRUD. Reserved for the identity/RBAC root tables (User,
    Workspace, WorkspaceMember) that define workspace membership rather than
    belong to a workspace themselves — everything else is a
    ``WorkspaceScopedRepository``.
    """

    def get(self, record_id: UUID) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        statement = select(self.model).limit(limit).offset(offset)
        return list(self.session.execute(statement).scalars().all())


class WorkspaceScopedRepository[ModelT: UUIDPrimaryKeyMixin](_SessionBoundRepository[ModelT]):
    """Every read goes through ``_scoped_select`` so a caller cannot bypass the
    workspace boundary AGENTS.md requires — unlike ``Repository``, there is no
    unscoped ``get``/``list`` to accidentally reach for instead.
    """

    def get_for_workspace(self, workspace_id: UUID, record_id: UUID) -> ModelT | None:
        statement = self._scoped_select(workspace_id).where(self.model.id == record_id)
        return self.session.execute(statement).scalar_one_or_none()

    def list_for_workspace(
        self, workspace_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[ModelT]:
        statement = self._scoped_select(workspace_id).limit(limit).offset(offset)
        return list(self.session.execute(statement).scalars().all())

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[ModelT]]:
        raise NotImplementedError
