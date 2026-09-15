"""End-to-end HTTP tests for the run lifecycle: workspace -> mission -> run
-> approval -> completion -> artifacts/audit (ARCHITECTURE.md section 9).

Uses TestClient + SQLite (dependency override) + FakeLLMProvider /
FakeEmbeddingProvider via a monkeypatched runtime factory -- no live
Postgres/Redis/Ollama/Docker required (AGENTS.md). TestClient runs
BackgroundTasks synchronously as part of each request, so the flow below
reads top-to-bottom exactly as it happens.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.artifacts as artifacts_router
import app.services.runs as run_service
from app.api.deps import get_db_session
from app.events.audit import PostgresAuditSink
from app.llm.fake import FakeLLMProvider
from app.main import app
from app.models import Base
from app.models.identity import User, WorkspaceMember, WorkspaceRole
from app.models.knowledge import KnowledgeChunk
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.schemas.planning import DraftPlan, DraftTask
from app.workflows.runtime import AegisRuntime

DATA_ROOT = Path(__file__).parents[3] / "data" / "demo"
DATASET = str(DATA_ROOT / "sales_data.csv")
HEADERS = {"X-Aegis-Identity-Subject": "operator@example.test"}
OTHER_HEADERS = {"X-Aegis-Identity-Subject": "someone-else@example.test"}


def _llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
    if response_model is DraftPlan:
        return DraftPlan(
            rationale="test",
            tasks=[DraftTask(agent="analyst", description="analyze")],  # type: ignore[arg-type]
        )
    if response_model.__name__ == "_Critique":
        return response_model()
    if response_model.__name__ == "_Narrative":
        return response_model(
            executive_summary="Test executive summary.", recommendations=["Test recommendation."]
        )
    raise AssertionError(f"Unexpected response_model: {response_model}")


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name != KnowledgeChunk.__tablename__
    ]
    Base.metadata.create_all(engine, tables=tables)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
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

    checkpoint_path = tmp_path / "runtime-checkpoints.sqlite"

    def fake_build_runtime(workspace_id: UUID) -> AegisRuntime:
        return AegisRuntime(
            DATA_ROOT,
            checkpoint_path=checkpoint_path,
            llm=FakeLLMProvider(factory=_llm_factory),
            embeddings=FakeEmbeddingProvider(),
            audit=PostgresAuditSink(session_factory=test_session_scope),
        )

    # Background tasks (execute_run_in_background, resume_run_in_background,
    # _sync_run_from_state, artifact writes) open their own sessions via
    # module-level session_scope/get_settings rather than FastAPI's
    # dependency injection, since they run outside any request -- patch
    # those references directly rather than app.dependency_overrides.
    # app.api.v1.artifacts also has its own `get_settings` import (to resolve
    # a downloaded artifact's path against artifact_root), so it needs the
    # same override or it checks containment against the real default.
    monkeypatch.setattr(run_service, "session_scope", test_session_scope)
    monkeypatch.setattr(run_service, "build_runtime_for_workspace", fake_build_runtime)
    test_settings = run_service.get_settings().model_copy(
        update={"artifact_root": str(tmp_path / "artifacts")}
    )
    monkeypatch.setattr(run_service, "get_settings", lambda: test_settings)
    monkeypatch.setattr(artifacts_router, "get_settings", lambda: test_settings)

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _create_workspace(client: TestClient, name: str = "Acme") -> str:
    response = client.post("/api/v1/workspaces", json={"name": name}, headers=HEADERS)
    assert response.status_code == 201, response.text
    workspace_id: str = response.json()["id"]
    return workspace_id


def _create_mission(client: TestClient, workspace_id: str) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/missions",
        json={
            "raw_request": "Analyze sales performance.",
            "objective": "Analyze sales performance and produce an executive summary.",
            "context": {"dataset_path": DATASET},
        },
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    mission_id: str = response.json()["id"]
    return mission_id


def test_full_mission_to_completed_run_flow(client: TestClient) -> None:
    workspace_id = _create_workspace(client)
    mission_id = _create_mission(client, workspace_id)

    run_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/missions/{mission_id}/runs", headers=HEADERS
    )
    assert run_response.status_code == 202, run_response.text
    run_id = run_response.json()["run_id"]

    detail = client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run_id}", headers=HEADERS
    ).json()
    assert detail["status"] == "awaiting_approval"

    approve_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/runs/{run_id}/approvals",
        json={"decision": "approve"},
        headers=HEADERS,
    )
    assert approve_response.status_code == 200, approve_response.text

    detail = client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run_id}", headers=HEADERS
    ).json()
    assert detail["status"] == "completed"
    assert detail["final_report"]["qa_status"] == "PASS"
    assert detail["final_report"]["compliance_verdict"] == "pass"

    artifacts = client.get(
        f"/api/v1/workspaces/{workspace_id}/missions/{mission_id}/artifacts", headers=HEADERS
    ).json()
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_type"] == "report"
    assert artifacts[0]["metadata"]["qa_status"] == "PASS"

    content_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/artifacts/{artifacts[0]['id']}/content",
        headers=HEADERS,
    )
    assert content_response.status_code == 200
    assert content_response.headers["content-type"].startswith("application/json")
    assert content_response.json()["qa_status"] == "PASS"

    mission_runs = client.get(
        f"/api/v1/workspaces/{workspace_id}/missions/{mission_id}/runs", headers=HEADERS
    ).json()
    assert [run["id"] for run in mission_runs] == [run_id]
    assert mission_runs[0]["status"] == "completed"

    audit_events = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit-events",
        params={"run_id": run_id},
        headers=HEADERS,
    ).json()
    assert any(event["event_type"] == "execution.completed" for event in audit_events)

    mission = client.get(
        f"/api/v1/workspaces/{workspace_id}/missions/{mission_id}", headers=HEADERS
    ).json()
    assert mission["status"] == "completed"


def test_plan_rejection_fails_the_run(client: TestClient) -> None:
    workspace_id = _create_workspace(client)
    mission_id = _create_mission(client, workspace_id)
    run_id = client.post(
        f"/api/v1/workspaces/{workspace_id}/missions/{mission_id}/runs", headers=HEADERS
    ).json()["run_id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/runs/{run_id}/approvals",
        json={"decision": "reject", "reason": "not needed"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


def test_cancel_requests_cooperative_cancellation(client: TestClient) -> None:
    workspace_id = _create_workspace(client)
    mission_id = _create_mission(client, workspace_id)
    run_id = client.post(
        f"/api/v1/workspaces/{workspace_id}/missions/{mission_id}/runs", headers=HEADERS
    ).json()["run_id"]

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/runs/{run_id}/cancel", headers=HEADERS
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancel_requested"

    detail = client.get(
        f"/api/v1/workspaces/{workspace_id}/runs/{run_id}", headers=HEADERS
    ).json()
    assert detail["status"] == "cancel_requested"


def test_missing_identity_header_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces")
    assert response.status_code == 401


def test_non_member_gets_404_not_403(client: TestClient) -> None:
    workspace_id = _create_workspace(client)
    response = client.get(f"/api/v1/workspaces/{workspace_id}/missions", headers=OTHER_HEADERS)
    assert response.status_code == 404


def test_viewer_role_cannot_create_mission(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    workspace_id = _create_workspace(client)

    # Directly seed a second user as a VIEWER member -- there is no invite
    # endpoint in scope for this phase, so this is done at the data layer.
    with session_factory() as session:
        user_row = User(
            identity_subject=OTHER_HEADERS["X-Aegis-Identity-Subject"], display_name="Other"
        )
        session.add(user_row)
        session.flush()
        session.add(
            WorkspaceMember(
                workspace_id=UUID(workspace_id), user_id=user_row.id, role=WorkspaceRole.VIEWER
            )
        )
        session.commit()

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/missions",
        json={"raw_request": "x", "objective": "x"},
        headers=OTHER_HEADERS,
    )
    assert response.status_code == 403
