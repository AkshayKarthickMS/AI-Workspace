"""Run lifecycle use cases (ARCHITECTURE.md section 6, section 9): starting a
run, resolving its approval/escalation gates, and keeping the lightweight
Postgres ``runs``/``missions`` projection in sync with the LangGraph
checkpoint that is the actual source of truth for live run state (see
``AegisRuntime.get_state``). Background functions here open their own
session rather than reusing a request-scoped one -- they run on a
threadpool thread well after the triggering request has returned.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import (
    ArtifactRepository,
    MissionPlanRepository,
    MissionRepository,
    RunRepository,
)
from app.db.session import session_scope
from app.models.artifact import Artifact
from app.models.mission import MissionPlan, MissionStatus, PlanStatus
from app.models.run import Run, RunStatus
from app.services.missions import domain_mission_from_row
from app.services.runtime_factory import build_runtime_for_workspace
from app.workflows.checkpoints import CheckpointNotFoundError
from app.workflows.state import AegisState, ExecutionStatus

logger = logging.getLogger(__name__)


class RunNotFoundError(LookupError):
    """Raised when a run has no persisted row or checkpoint in this workspace."""


class InvalidRunActionError(ValueError):
    """Raised when an action doesn't apply to a run's current status."""


def start_run(session: Session, *, workspace_id: UUID, mission_id: UUID) -> Run:
    mission_row = MissionRepository(session).get_for_workspace(workspace_id, mission_id)
    if mission_row is None:
        raise RunNotFoundError("Mission not found")

    execution_id = uuid4()
    run_row = RunRepository(session).add(
        Run(id=execution_id, mission_id=mission_id, started_at=datetime.now(UTC))
    )
    mission_row.status = MissionStatus.RUNNING
    return run_row


def execute_run_in_background(*, execution_id: UUID, mission_id: UUID, workspace_id: UUID) -> None:
    with session_scope() as session:
        mission_row = MissionRepository(session).get_for_workspace(workspace_id, mission_id)
        if mission_row is None:
            logger.error("run_background_mission_missing execution_id=%s", execution_id)
            return
        domain_mission = domain_mission_from_row(mission_row)

    try:
        with build_runtime_for_workspace(workspace_id) as runtime:
            state = runtime.run(domain_mission, execution_id=execution_id)
    except Exception:
        logger.exception("run_background_execution_failed execution_id=%s", execution_id)
        return

    with session_scope() as session:
        _sync_run_from_state(
            session,
            workspace_id=workspace_id,
            mission_id=mission_id,
            execution_id=execution_id,
            state=state,
        )


def resume_run_in_background(*, execution_id: UUID, mission_id: UUID, workspace_id: UUID) -> None:
    try:
        with build_runtime_for_workspace(workspace_id) as runtime:
            state = runtime.resume(execution_id)
    except Exception:
        logger.exception("run_background_resume_failed execution_id=%s", execution_id)
        return

    with session_scope() as session:
        _sync_run_from_state(
            session,
            workspace_id=workspace_id,
            mission_id=mission_id,
            execution_id=execution_id,
            state=state,
        )


def get_run_state(*, workspace_id: UUID, run_id: UUID) -> AegisState:
    with build_runtime_for_workspace(workspace_id) as runtime:
        try:
            return runtime.get_state(run_id)
        except CheckpointNotFoundError as exc:
            raise RunNotFoundError(str(exc)) from exc


def resolve_approval(
    *,
    workspace_id: UUID,
    run_id: UUID,
    decision: Literal["approve", "reject"],
    reason: str | None,
    actor: str,
) -> AegisState:
    with build_runtime_for_workspace(workspace_id) as runtime:
        try:
            state = runtime.get_state(run_id)
        except CheckpointNotFoundError as exc:
            raise RunNotFoundError(str(exc)) from exc

        run_status = ExecutionStatus(state["status"])
        if run_status == ExecutionStatus.AWAITING_APPROVAL:
            if decision == "approve":
                return runtime.approve_plan(run_id, approved_by=actor)
            return runtime.reject_plan(run_id, reason=reason, rejected_by=actor)
        if run_status == ExecutionStatus.AWAITING_ESCALATION:
            return runtime.resolve_escalation(
                run_id,
                approved=(decision == "approve"),
                resolved_by=actor,
                resolution_reference=reason,
            )
        raise InvalidRunActionError(
            f"Run is not awaiting a decision (status={run_status.value!r})"
        )


def request_cancellation(*, workspace_id: UUID, run_id: UUID) -> AegisState:
    with build_runtime_for_workspace(workspace_id) as runtime:
        try:
            return runtime.request_cancellation(run_id)
        except CheckpointNotFoundError as exc:
            raise RunNotFoundError(str(exc)) from exc


def _sync_run_from_state(
    session: Session,
    *,
    workspace_id: UUID,
    mission_id: UUID,
    execution_id: UUID,
    state: AegisState,
) -> None:
    run_row = RunRepository(session).get_for_workspace(workspace_id, execution_id)
    if run_row is None:
        return

    run_row.status = RunStatus(state["status"])
    plan_data = state.get("plan")
    if plan_data is not None and run_row.plan_id is None:
        approval = state.get("approval") or {}
        plan_status = (
            PlanStatus.APPROVED if approval.get("status") == "approved" else PlanStatus.DRAFT
        )
        plan_row = MissionPlanRepository(session).add(
            MissionPlan(mission_id=mission_id, plan=plan_data, status=plan_status)
        )
        run_row.plan_id = plan_row.id

    if run_row.status == RunStatus.COMPLETED:
        run_row.completed_at = datetime.now(UTC)
        _set_mission_status(session, workspace_id, mission_id, MissionStatus.COMPLETED)
        final_report = state.get("final_report")
        if final_report is not None:
            _store_final_report_artifact(
                session, mission_id=mission_id, run_id=execution_id, final_report=final_report
            )
    elif run_row.status == RunStatus.FAILED:
        run_row.completed_at = datetime.now(UTC)
        last_error = state.get("last_error") or {}
        run_row.error_summary = str(last_error.get("message")) if last_error else None
        _set_mission_status(session, workspace_id, mission_id, MissionStatus.FAILED)


def _set_mission_status(
    session: Session, workspace_id: UUID, mission_id: UUID, status: MissionStatus
) -> None:
    mission_row = MissionRepository(session).get_for_workspace(workspace_id, mission_id)
    if mission_row is not None:
        mission_row.status = status


def _store_final_report_artifact(
    session: Session, *, mission_id: UUID, run_id: UUID, final_report: dict[str, Any]
) -> None:
    """Write the report (and its embedded slide deck) to the local artifact
    store and record it (ARCHITECTURE.md section 8; a Day-1 local-volume
    store, not yet the S3-compatible one the scalability path calls for)."""

    settings = get_settings()
    artifact_root = Path(settings.artifact_root).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(final_report, indent=2, sort_keys=True).encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()
    file_path = artifact_root / f"{run_id}-report.json"
    file_path.write_bytes(payload)

    ArtifactRepository(session).add(
        Artifact(
            mission_id=mission_id,
            run_id=run_id,
            artifact_type="report",
            storage_uri=file_path.as_uri(),
            checksum=checksum,
            artifact_metadata={
                "title": final_report.get("title"),
                "qa_status": final_report.get("qa_status"),
                "compliance_verdict": final_report.get("compliance_verdict"),
                "has_slide_deck": final_report.get("slide_deck") is not None,
            },
        )
    )
