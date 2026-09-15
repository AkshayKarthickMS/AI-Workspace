"""SQLAlchemy ORM models for the persistence schema (see ARCHITECTURE.md section 8).

Every model module is imported here so ``Base.metadata`` is fully populated
for anything that imports only ``app.models`` -- Alembic's ``env.py`` in
particular relies on this rather than importing each table module itself.
"""

from app.models.artifact import Artifact
from app.models.audit import AuditEventRecord
from app.models.base import Base
from app.models.compliance import ComplianceReview
from app.models.identity import User, Workspace, WorkspaceMember, WorkspaceRole
from app.models.knowledge import (
    EMBEDDING_DIMENSIONS,
    IngestionStatus,
    KnowledgeChunk,
    KnowledgeDocument,
)
from app.models.mission import Mission, MissionPlan, MissionStatus, PlanStatus, PlanStep
from app.models.run import Run, RunCheckpoint, RunStatus
from app.models.tool_execution import (
    CodeExecution,
    SqlQuery,
    ToolExecution,
    ToolExecutionStatus,
    ToolRiskLevel,
)

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "Artifact",
    "AuditEventRecord",
    "Base",
    "CodeExecution",
    "ComplianceReview",
    "IngestionStatus",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Mission",
    "MissionPlan",
    "MissionStatus",
    "PlanStatus",
    "PlanStep",
    "Run",
    "RunCheckpoint",
    "RunStatus",
    "SqlQuery",
    "ToolExecution",
    "ToolExecutionStatus",
    "ToolRiskLevel",
    "User",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceRole",
]
