"""Compliance review repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.compliance import ComplianceReview
from app.models.mission import Mission
from app.models.run import Run


class ComplianceReviewRepository(WorkspaceScopedRepository[ComplianceReview]):
    model = ComplianceReview

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[ComplianceReview]]:
        return (
            select(ComplianceReview)
            .join(Run, Run.id == ComplianceReview.run_id)
            .join(Mission, Mission.id == Run.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )
