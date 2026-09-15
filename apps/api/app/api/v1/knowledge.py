"""Knowledge base routes (ARCHITECTURE.md section 9). Ingestion is explicit
and audited (AGENTS.md) -- this is the only path that writes to the
retrieval corpus; agents only ever read it."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_workspace_role
from app.models.identity import WorkspaceMember, WorkspaceRole
from app.models.knowledge import KnowledgeDocument
from app.services.knowledge import ingest_document, list_documents

router = APIRouter(prefix="/workspaces/{workspace_id}/knowledge/documents", tags=["knowledge"])


class KnowledgeDocumentCreateRequest(BaseModel):
    source_uri: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    source_uri: str
    ingestion_status: str
    checksum: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: KnowledgeDocument) -> KnowledgeDocumentResponse:
        return cls(
            id=row.id,
            source_uri=row.source_uri,
            ingestion_status=row.ingestion_status.value,
            checksum=row.checksum,
            created_at=row.created_at,
        )


@router.post("", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
def ingest_document_route(
    workspace_id: UUID,
    body: KnowledgeDocumentCreateRequest,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OPERATOR)),
) -> KnowledgeDocumentResponse:
    row = ingest_document(
        session,
        workspace_id=workspace_id,
        source_uri=body.source_uri,
        text=body.text,
        source_metadata=body.source_metadata,
    )
    return KnowledgeDocumentResponse.from_row(row)


@router.get("", response_model=list[KnowledgeDocumentResponse])
def list_documents_route(
    workspace_id: UUID,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> list[KnowledgeDocumentResponse]:
    rows = list_documents(session, workspace_id=workspace_id)
    return [KnowledgeDocumentResponse.from_row(row) for row in rows]
