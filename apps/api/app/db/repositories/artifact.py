"""Artifact repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.artifact import Artifact
from app.models.mission import Mission


class ArtifactRepository(WorkspaceScopedRepository[Artifact]):
    model = Artifact

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[Artifact]]:
        return (
            select(Artifact)
            .join(Mission, Mission.id == Artifact.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )

    def list_for_mission(self, workspace_id: UUID, mission_id: UUID) -> list[Artifact]:
        statement = self._scoped_select(workspace_id).where(Artifact.mission_id == mission_id)
        return list(self.session.execute(statement).scalars().all())
