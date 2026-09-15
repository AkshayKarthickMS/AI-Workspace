"""Run routes: start, detail, approvals/escalations, resume, cancel, and SSE
(ARCHITECTURE.md section 9)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session, require_workspace_role
from app.core.config import get_settings
from app.db.repositories import RunRepository
from app.events.redis_bus import run_event_stream_key
from app.models.identity import User, WorkspaceMember, WorkspaceRole
from app.models.run import Run
from app.services import runs as run_service
from app.workflows.state import AegisState, ExecutionStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runs"])


class RunStartResponse(BaseModel):
    run_id: UUID
    status: str


class RunSummaryResponse(BaseModel):
    """A run history row -- the lightweight Postgres projection
    (ARCHITECTURE.md §6), kept in sync opportunistically. Use
    ``RunDetailResponse`` for the authoritative live state of one run."""

    id: UUID
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None

    @classmethod
    def from_row(cls, row: Run) -> RunSummaryResponse:
        return cls(
            id=row.id,
            status=row.status.value,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            error_summary=row.error_summary,
        )


class RunDetailResponse(BaseModel):
    run_id: UUID
    mission_id: UUID
    status: str
    plan: dict[str, Any] | None = None
    tasks: dict[str, dict[str, Any]] | None = None
    approval: dict[str, Any] | None = None
    escalation: dict[str, Any] | None = None
    qa_result: dict[str, Any] | None = None
    compliance_result: dict[str, Any] | None = None
    final_report: dict[str, Any] | None = None
    last_error: dict[str, Any] | None = None


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)


def _to_detail(state: AegisState) -> RunDetailResponse:
    return RunDetailResponse(
        run_id=UUID(state["execution_id"]),
        mission_id=UUID(state["mission_id"]),
        status=state["status"],
        plan=state.get("plan"),
        tasks=state.get("tasks"),
        approval=state.get("approval"),
        escalation=state.get("escalation"),
        qa_result=state.get("qa_result"),
        compliance_result=state.get("compliance_result"),
        final_report=state.get("final_report"),
        last_error=state.get("last_error"),
    )


@router.post(
    "/workspaces/{workspace_id}/missions/{mission_id}/runs",
    response_model=RunStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_run_route(
    workspace_id: UUID,
    mission_id: UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OPERATOR)),
) -> RunStartResponse:
    try:
        run_row = run_service.start_run(session, workspace_id=workspace_id, mission_id=mission_id)
    except run_service.RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.flush()
    run_id = run_row.id
    background_tasks.add_task(
        run_service.execute_run_in_background,
        execution_id=run_id,
        mission_id=mission_id,
        workspace_id=workspace_id,
    )
    return RunStartResponse(run_id=run_id, status=run_row.status.value)


@router.get(
    "/workspaces/{workspace_id}/missions/{mission_id}/runs",
    response_model=list[RunSummaryResponse],
)
def list_mission_runs_route(
    workspace_id: UUID,
    mission_id: UUID,
    session: Session = Depends(get_db_session),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> list[RunSummaryResponse]:
    rows = RunRepository(session).list_for_mission(workspace_id, mission_id)
    return [RunSummaryResponse.from_row(row) for row in rows]


@router.get("/workspaces/{workspace_id}/runs/{run_id}", response_model=RunDetailResponse)
def get_run_route(
    workspace_id: UUID,
    run_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> RunDetailResponse:
    try:
        state = run_service.get_run_state(workspace_id=workspace_id, run_id=run_id)
    except run_service.RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_detail(state)


@router.post(
    "/workspaces/{workspace_id}/runs/{run_id}/approvals", response_model=RunDetailResponse
)
def resolve_approval_route(
    workspace_id: UUID,
    run_id: UUID,
    body: ApprovalDecisionRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.REVIEWER)),
) -> RunDetailResponse:
    try:
        state = run_service.resolve_approval(
            workspace_id=workspace_id,
            run_id=run_id,
            decision=body.decision,
            reason=body.reason,
            actor=user.identity_subject,
        )
    except run_service.RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except run_service.InvalidRunActionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if ExecutionStatus(state["status"]) != ExecutionStatus.FAILED:
        # Approved (or an escalation approval): schedule the continuation.
        # A rejection already set status=FAILED, terminal, nothing to resume.
        background_tasks.add_task(
            run_service.resume_run_in_background,
            execution_id=run_id,
            mission_id=UUID(state["mission_id"]),
            workspace_id=workspace_id,
        )
    return _to_detail(state)


@router.post(
    "/workspaces/{workspace_id}/runs/{run_id}/resume",
    response_model=RunDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resume_run_route(
    workspace_id: UUID,
    run_id: UUID,
    background_tasks: BackgroundTasks,
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OPERATOR)),
) -> RunDetailResponse:
    try:
        state = run_service.get_run_state(workspace_id=workspace_id, run_id=run_id)
    except run_service.RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    background_tasks.add_task(
        run_service.resume_run_in_background,
        execution_id=run_id,
        mission_id=UUID(state["mission_id"]),
        workspace_id=workspace_id,
    )
    return _to_detail(state)


@router.post("/workspaces/{workspace_id}/runs/{run_id}/cancel", response_model=RunDetailResponse)
def cancel_run_route(
    workspace_id: UUID,
    run_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OPERATOR)),
) -> RunDetailResponse:
    try:
        state = run_service.request_cancellation(workspace_id=workspace_id, run_id=run_id)
    except run_service.RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_detail(state)


def format_sse_event(entry_id: bytes | str, fields: dict[Any, Any]) -> str:
    """Pure formatting, split out so it's unit-testable without a live Redis
    connection or the surrounding async generator."""

    eid = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
    payload = fields.get(b"payload", fields.get("payload"))
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return f"id: {eid}\ndata: {payload}\n\n"


@router.get("/workspaces/{workspace_id}/runs/{run_id}/events")
async def stream_run_events_route(
    request: Request,
    workspace_id: UUID,
    run_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.VIEWER)),
) -> StreamingResponse:
    """Server-sent events for one run's audit trail (ARCHITECTURE.md section
    11), tailing the Redis Stream ``RedisEventBusSink`` publishes to.
    Reconnecting clients replay up to the stream's retained window (see
    ``RedisEventBusSink.STREAM_MAXLEN``) by starting from id "0"."""

    return StreamingResponse(
        _event_source(request, run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _event_source(request: Request, run_id: UUID) -> AsyncIterator[str]:
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url)
    stream_key = run_event_stream_key(run_id)
    last_id = "0"
    try:
        yield "retry: 2000\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                response = await client.xread({stream_key: last_id}, count=50, block=10_000)
            except Exception:
                logger.warning("sse_redis_unavailable run_id=%s", run_id, exc_info=True)
                yield ": redis unavailable, retrying\n\n"
                await asyncio.sleep(5)
                continue
            if not response:
                yield ": heartbeat\n\n"
                continue
            for _stream_name, entries in response:
                for entry_id, fields in entries:
                    last_id = entry_id
                    yield format_sse_event(entry_id, fields)
    finally:
        await client.aclose()
