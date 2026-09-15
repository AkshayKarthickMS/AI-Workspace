"""Dataset upload routes (ARCHITECTURE.md section 9). Lets a workspace member
upload their own CSV/Excel file to analyze instead of requiring one already
staged on the server filesystem -- the file is written under the configured
data root so the existing Analyst-tool allowed-root check applies to it
unchanged."""

from __future__ import annotations

import io
import re
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import require_workspace_role
from app.core.config import get_settings
from app.models.identity import WorkspaceMember, WorkspaceRole

router = APIRouter(prefix="/workspaces/{workspace_id}/datasets", tags=["datasets"])

_ALLOWED_EXTENSIONS = {".csv", ".xlsx"}
# Generous for an analysis file, bounded to protect the free-tier deployment's
# ephemeral disk from an accidental multi-hundred-MB upload.
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


class DatasetUploadResponse(BaseModel):
    dataset_path: str
    original_filename: str
    rows: int
    columns: int


@router.post("", response_model=DatasetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset_route(
    workspace_id: uuid.UUID,
    file: UploadFile,
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OPERATOR)),
) -> DatasetUploadResponse:
    original_name = file.filename or "dataset"
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv or .xlsx files are accepted.",
        )

    contents = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit.",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )

    frame = _read_tabular(contents, suffix)
    if frame.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded dataset has no rows."
        )

    settings = get_settings()
    upload_dir = Path(settings.data_root) / "uploads" / str(workspace_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_stem = _UNSAFE_NAME_CHARS.sub("_", Path(original_name).stem)[:80] or "dataset"
    dest = upload_dir / f"{uuid.uuid4().hex}_{safe_stem}.csv"
    frame.to_csv(dest, index=False)

    return DatasetUploadResponse(
        dataset_path=str(dest).replace("\\", "/"),
        original_filename=original_name,
        rows=int(len(frame)),
        columns=int(len(frame.columns)),
    )


def _read_tabular(contents: bytes, suffix: str) -> pd.DataFrame:
    buffer = io.BytesIO(contents)
    try:
        if suffix == ".csv":
            return pd.read_csv(buffer)
        return pd.read_excel(buffer)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse the uploaded file: {exc}",
        ) from exc
