"""Run and run-checkpoint repositories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.mission import Mission
from app.models.run import Run, RunCheckpoint


class RunRepository(WorkspaceScopedRepository[Run]):
    model = Run

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[Run]]:
        return (
            select(Run)
            .join(Mission, Mission.id == Run.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )

    def list_for_mission(self, workspace_id: UUID, mission_id: UUID) -> list[Run]:
        statement = (
            self._scoped_select(workspace_id)
            .where(Run.mission_id == mission_id)
            .order_by(Run.created_at.desc())
        )
        return list(self.session.execute(statement).scalars().all())


class RunCheckpointRepository(WorkspaceScopedRepository[RunCheckpoint]):
    model = RunCheckpoint

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[RunCheckpoint]]:
        return (
            select(RunCheckpoint)
            .join(Run, Run.id == RunCheckpoint.run_id)
            .join(Mission, Mission.id == Run.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )

    def list_for_run(self, workspace_id: UUID, run_id: UUID) -> list[RunCheckpoint]:
        statement = (
            self._scoped_select(workspace_id)
            .where(RunCheckpoint.run_id == run_id)
            .order_by(RunCheckpoint.sequence)
        )
        return list(self.session.execute(statement).scalars().all())
