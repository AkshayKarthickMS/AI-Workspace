"""Tool-execution, SQL-query, and code-execution repositories."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select

from app.db.repositories.base import WorkspaceScopedRepository
from app.models.mission import Mission
from app.models.run import Run
from app.models.tool_execution import CodeExecution, SqlQuery, ToolExecution


class ToolExecutionRepository(WorkspaceScopedRepository[ToolExecution]):
    model = ToolExecution

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[ToolExecution]]:
        return (
            select(ToolExecution)
            .join(Run, Run.id == ToolExecution.run_id)
            .join(Mission, Mission.id == Run.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )


class SqlQueryRepository(WorkspaceScopedRepository[SqlQuery]):
    model = SqlQuery

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[SqlQuery]]:
        return (
            select(SqlQuery)
            .join(Run, Run.id == SqlQuery.run_id)
            .join(Mission, Mission.id == Run.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )


class CodeExecutionRepository(WorkspaceScopedRepository[CodeExecution]):
    model = CodeExecution

    def _scoped_select(self, workspace_id: UUID) -> Select[tuple[CodeExecution]]:
        return (
            select(CodeExecution)
            .join(Run, Run.id == CodeExecution.run_id)
            .join(Mission, Mission.id == Run.mission_id)
            .where(Mission.workspace_id == workspace_id)
        )
