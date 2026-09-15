"""Artifact listing and content-download routes (ARCHITECTURE.md section 9)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_workspace_role
from app.core.config import get_settings
from app.db.repositories import ArtifactRepository
from app.models.artifact import Artifact
from app.models.identity import WorkspaceMember, WorkspaceRole

router = APIRouter(
    prefix="/workspaces/{workspace_id}/missions/{mission_id}/artifacts", tags=["artifacts"]
)
content_router = APIRouter(prefix="/workspaces/{workspace_id}/artifacts", tags=["artifacts"])


class ArtifactResponse(BaseModel):
    id: UUID
    run_id: UUID | None
    artifact_type: str
    storage_uri: str
    checksum: str
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_row(cls, row: Artifact) -> ArtifactResponse:
        return cls(
            id=row.id,
            run_id=row.run_id,
            artifact_type=row.artifact_type,
            storage_uri=row.storage_uri,
            checksum=row.checksum,
            metadata=row.artifact_metadata,
            created_at=row.created_at,
        )


@router.get("", response_model=list[ArtifactResponse])
def list_artifacts_route(
    workspace_id: UUID,
    mission_id: UUID,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> list[ArtifactResponse]:
    rows = ArtifactRepository(session).list_for_mission(workspace_id, mission_id)
    return [ArtifactResponse.from_row(row) for row in rows]


@content_router.get("/{artifact_id}/content")
def get_artifact_content_route(
    workspace_id: UUID,
    artifact_id: UUID,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> Response:
    """Serve an artifact's raw file content (e.g. the report JSON, with its
    embedded slide deck) so the frontend can render or download it --
    ``storage_uri`` alone is a ``file://`` URI a browser can't fetch."""

    row = ArtifactRepository(session).get_for_workspace(workspace_id, artifact_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    parsed = urlparse(row.storage_uri)
    if parsed.scheme != "file":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This artifact's storage backend does not support content download yet",
        )
    file_path = Path(url2pathname(parsed.path)).resolve()

    # storage_uri is always server-generated (never user input), but this is
    # a cheap defense-in-depth check regardless (AGENTS.md).
    artifact_root = Path(get_settings().artifact_root).resolve()
    if artifact_root != file_path and artifact_root not in file_path.parents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Artifact path is outside the configured artifact store",
        )
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file is missing on disk"
        )

    media_type = (
        "application/json" if row.artifact_type == "report" else "application/octet-stream"
    )
    return Response(
        content=file_path.read_bytes(),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'},
    )
