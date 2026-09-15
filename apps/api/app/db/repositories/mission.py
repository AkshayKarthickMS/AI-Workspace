"""Mission, plan, and plan-step repositories (ARCHITECTURE.md section 6)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.mission import Mission, MissionPlan, PlanStep


class MissionRepository(WorkspaceScopedRepository[Mission]):
    model = Mission

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[Mission]]:
        return select(Mission).where(Mission.workspace_id == workspace_id)


class MissionPlanRepository(WorkspaceScopedRepository[MissionPlan]):
    model = MissionPlan

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[MissionPlan]]:
        return (
            select(MissionPlan)
            .join(Mission, Mission.id == MissionPlan.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )

    def list_for_mission(self, workspace_id: UUID, mission_id: UUID) -> list[MissionPlan]:
        statement = self._scoped_select(workspace_id).where(MissionPlan.mission_id == mission_id)
        return list(self.session.execute(statement).scalars().all())


class PlanStepRepository(WorkspaceScopedRepository[PlanStep]):
    model = PlanStep

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[PlanStep]]:
        return (
            select(PlanStep)
            .join(MissionPlan, MissionPlan.id == PlanStep.plan_id)
            .join(Mission, Mission.id == MissionPlan.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )

    def list_for_plan(self, workspace_id: UUID, plan_id: UUID) -> list[PlanStep]:
        statement = self._scoped_select(workspace_id).where(PlanStep.plan_id == plan_id)
        return list(self.session.execute(statement).scalars().all())
