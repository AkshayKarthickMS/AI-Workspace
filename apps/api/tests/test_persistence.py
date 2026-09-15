"""Repository and persistent-audit-sink tests against a throwaway SQLite DB.

PostgreSQL + pgvector is the real target (ARCHITECTURE.md section 8); this
covers everything except ``KnowledgeChunk``'s vector column, which pgvector's
SQLAlchemy type does not support outside Postgres — its table creation is
still exercised by the Alembic migration itself. Full Postgres+pgvector
integration coverage is Phase 7 (see CLAUDE.md's roadmap), against a
disposable real Postgres instance rather than SQLite.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.repositories import (
    ArtifactRepository,
    AuditEventRepository,
    MissionPlanRepository,
    MissionRepository,
    PlanStepRepository,
    RunRepository,
    UserRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from app.events.audit import AuditEvent, PostgresAuditSink
from app.models import (
    Artifact,
    Base,
    Mission,
    MissionPlan,
    PlanStep,
    Run,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)
from app.models.knowledge import KnowledgeChunk
from app.schemas.agents import AgentRole, TaskStatus

SessionFactory = sessionmaker[Session]


@pytest.fixture
def session_factory() -> SessionFactory:
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


@contextmanager
def _session(factory: SessionFactory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_workspace(session: Session, *, slug: str = "acme") -> tuple[Workspace, User]:
    user = UserRepository(session).add(
        User(identity_subject=f"local|{slug}", display_name="Test User")
    )
    workspace = WorkspaceRepository(session).add(Workspace(name=slug.title(), slug=slug))
    WorkspaceMemberRepository(session).add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.ADMIN)
    )
    return workspace, user


def test_workspace_scoped_repository_isolates_other_workspaces(
    session_factory: SessionFactory,
) -> None:
    with _session(session_factory) as session:
        workspace, user = _seed_workspace(session, slug="acme")
        other_workspace, _ = _seed_workspace(session, slug="other")
        MissionRepository(session).add(
            Mission(
                workspace_id=workspace.id,
                title="Prepare business review",
                raw_request="Prepare next month's business review.",
                created_by=user.id,
            )
        )
        MissionRepository(session).add(
            Mission(
                workspace_id=other_workspace.id,
                title="Unrelated mission",
                raw_request="...",
                created_by=user.id,
            )
        )

    with _session(session_factory) as session:
        missions = MissionRepository(session).list_for_workspace(workspace.id)
        assert [m.title for m in missions] == ["Prepare business review"]

        other_missions = MissionRepository(session).list_for_workspace(other_workspace.id)
        assert [m.title for m in other_missions] == ["Unrelated mission"]


def test_plan_step_round_trips_and_reuses_domain_task_id(
    session_factory: SessionFactory,
) -> None:
    task_id = uuid4()
    with _session(session_factory) as session:
        workspace, user = _seed_workspace(session)
        mission = MissionRepository(session).add(
            Mission(
                workspace_id=workspace.id,
                title="Analyze sales performance",
                raw_request="Analyze sales performance and produce an executive summary.",
                created_by=user.id,
            )
        )
        plan = MissionPlanRepository(session).add(
            MissionPlan(mission_id=mission.id, plan={"tasks": []})
        )
        PlanStepRepository(session).add(
            PlanStep(
                id=task_id,
                plan_id=plan.id,
                position=0,
                agent_role=AgentRole.RESEARCH,
                description="Collect approved evidence relevant to the mission.",
                dependencies=[],
                input={"query": "sales performance"},
            )
        )
        workspace_id = workspace.id

    with _session(session_factory) as session:
        step = PlanStepRepository(session).get_for_workspace(workspace_id, task_id)
        assert step is not None
        assert step.id == task_id
        assert step.agent_role == AgentRole.RESEARCH
        assert step.status == TaskStatus.PENDING


def test_run_and_artifact_are_workspace_scoped_through_mission(
    session_factory: SessionFactory,
) -> None:
    with _session(session_factory) as session:
        workspace, user = _seed_workspace(session)
        mission = MissionRepository(session).add(
            Mission(
                workspace_id=workspace.id,
                title="Analyze sales performance",
                raw_request="...",
                created_by=user.id,
            )
        )
        plan = MissionPlanRepository(session).add(
            MissionPlan(mission_id=mission.id, plan={"tasks": []})
        )
        run = RunRepository(session).add(Run(mission_id=mission.id, plan_id=plan.id))
        ArtifactRepository(session).add(
            Artifact(
                mission_id=mission.id,
                run_id=run.id,
                artifact_type="report",
                storage_uri="file:///artifacts/report.pdf",
                checksum="deadbeef",
            )
        )
        workspace_id, run_id = workspace.id, run.id

    with _session(session_factory) as session:
        assert RunRepository(session).get_for_workspace(workspace_id, run_id) is not None
        artifacts = ArtifactRepository(session).list_for_workspace(workspace_id)
        assert [a.artifact_type for a in artifacts] == ["report"]


def test_postgres_audit_sink_persists_events_and_keeps_in_memory_behavior(
    session_factory: SessionFactory,
) -> None:
    with _session(session_factory) as session:
        workspace, user = _seed_workspace(session)
        mission = MissionRepository(session).add(
            Mission(
                workspace_id=workspace.id,
                title="Analyze sales performance",
                raw_request="...",
                created_by=user.id,
            )
        )
        workspace_id, mission_id = workspace.id, mission.id

    sink = PostgresAuditSink(session_factory=lambda: _session(session_factory))
    event = AuditEvent(
        event_type="execution.created",
        actor="orchestrator",
        mission_id=mission_id,
        run_id=uuid4(),
        status="created",
    )
    sink.emit(event)

    # Base AuditSink behavior (in-memory list, useful for tests) is preserved.
    assert sink.events == [event]

    with _session(session_factory) as session:
        persisted = AuditEventRepository(session).list_for_workspace(workspace_id)
        assert [record.event_type for record in persisted] == ["execution.created"]
        assert persisted[0].id == event.event_id
