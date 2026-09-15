"""HTTP tests for the dataset upload route (ARCHITECTURE.md section 9) --
lets a workspace member stage their own CSV/Excel file for a mission instead
of requiring one already present on the server filesystem."""

from __future__ import annotations

import io
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.datasets as datasets_router
from app.api.deps import get_db_session
from app.main import app
from app.models import Base
from app.models.knowledge import KnowledgeChunk
from app.tools.tabular_analysis import GenericTabularAnalysisTool

HEADERS = {"X-Aegis-Identity-Subject": "operator@example.test"}
VIEWER_HEADERS = {"X-Aegis-Identity-Subject": "viewer@example.test"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [
        table for table in Base.metadata.sorted_tables if table.name != KnowledgeChunk.__tablename__
    ]
    Base.metadata.create_all(engine, tables=tables)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_session_scope() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def override_get_db_session() -> Iterator[Session]:
        with test_session_scope() as session:
            yield session

    test_settings = datasets_router.get_settings().model_copy(update={"data_root": str(tmp_path)})
    monkeypatch.setattr(datasets_router, "get_settings", lambda: test_settings)

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _create_workspace(client: TestClient) -> str:
    response = client.post("/api/v1/workspaces", json={"name": "Acme"}, headers=HEADERS)
    assert response.status_code == 201, response.text
    workspace_id: str = response.json()["id"]
    return workspace_id


def test_upload_csv_dataset_and_analyze_it(client: TestClient, tmp_path: Path) -> None:
    workspace_id = _create_workspace(client)
    csv_bytes = b"region,revenue\nNorth,100\nSouth,50\n"

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/datasets",
        files={"file": ("my_sales.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=HEADERS,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["rows"] == 2
    assert body["columns"] == 2
    assert body["original_filename"] == "my_sales.csv"

    # The returned path must be usable exactly as-is by the Analyst tool,
    # under the same allowed root the upload route wrote it into.
    tool = GenericTabularAnalysisTool(tmp_path)
    findings, _, summary = tool.analyze(body["dataset_path"])
    assert summary["rows"] == 2
    assert any("North" in finding.statement for finding in findings)


def test_upload_rejects_disallowed_extension(client: TestClient) -> None:
    workspace_id = _create_workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/datasets",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=HEADERS,
    )

    assert response.status_code == 400
    assert "csv" in response.json()["detail"].lower()


def test_upload_rejects_empty_file(client: TestClient) -> None:
    workspace_id = _create_workspace(client)

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/datasets",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        headers=HEADERS,
    )

    assert response.status_code == 400


def test_upload_requires_operator_role(client: TestClient) -> None:
    workspace_id = _create_workspace(client)
    # Auto-provisioning a brand-new identity as a workspace member isn't part
    # of this route -- a caller who was never added to the workspace gets the
    # same 404 as a nonexistent workspace (least information disclosure).
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/datasets",
        files={"file": ("sales.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
        headers=VIEWER_HEADERS,
    )

    assert response.status_code == 404
