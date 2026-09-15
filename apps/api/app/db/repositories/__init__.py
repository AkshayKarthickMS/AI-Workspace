"""Workspace-scoped repository layer (ARCHITECTURE.md section 6)."""

from app.db.repositories.artifact import ArtifactRepository
from app.db.repositories.audit import AuditEventRepository
from app.db.repositories.base import Repository, WorkspaceScopedRepository
from app.db.repositories.compliance import ComplianceReviewRepository
from app.db.repositories.identity import (
    UserRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from app.db.repositories.knowledge import KnowledgeChunkRepository, KnowledgeDocumentRepository
from app.db.repositories.mission import (
    MissionPlanRepository,
    MissionRepository,
    PlanStepRepository,
)
from app.db.repositories.run import RunCheckpointRepository, RunRepository
from app.db.repositories.tool_execution import (
    CodeExecutionRepository,
    SqlQueryRepository,
    ToolExecutionRepository,
)

__all__ = [
    "ArtifactRepository",
    "AuditEventRepository",
    "CodeExecutionRepository",
    "ComplianceReviewRepository",
    "KnowledgeChunkRepository",
    "KnowledgeDocumentRepository",
    "MissionPlanRepository",
    "MissionRepository",
    "PlanStepRepository",
    "Repository",
    "RunCheckpointRepository",
    "RunRepository",
    "SqlQueryRepository",
    "ToolExecutionRepository",
    "UserRepository",
    "WorkspaceMemberRepository",
    "WorkspaceRepository",
    "WorkspaceScopedRepository",
]
