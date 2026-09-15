"""Mission intake use cases (ARCHITECTURE.md section 6, section 9). Missions
are persisted as ``raw_request`` (the caller's original text) plus
``normalized_request`` (the validated domain ``Mission``, dumped to JSON) --
starting a run later re-validates it back via ``Mission.model_validate``."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.repositories import MissionRepository
from app.models.mission import Mission as MissionRow
from app.models.mission import MissionStatus
from app.schemas.agents import Mission as DomainMission


def create_mission(
    session: Session,
    *,
    workspace_id: UUID,
    created_by: UUID,
    raw_request: str,
    objective: str,
    constraints: list[str] | None = None,
    success_criteria: list[str] | None = None,
    context: dict[str, object] | None = None,
) -> MissionRow:
    # Generated once, shared by both: the row's primary key and the domain
    # Mission's own id must be the same UUID (Mission.mission_id has its own
    # independent default_factory, so leaving it unset would mint a second,
    # different UUID for "the same" mission).
    mission_id = uuid4()
    domain_mission = DomainMission(
        mission_id=mission_id,
        objective=objective,
        constraints=constraints or [],
        success_criteria=success_criteria or [],
        context=context or {},
    )
    return MissionRepository(session).add(
        MissionRow(
            id=mission_id,
            workspace_id=workspace_id,
            title=objective[:300],
            raw_request=raw_request,
            normalized_request=domain_mission.model_dump(mode="json"),
            status=MissionStatus.DRAFT,
            created_by=created_by,
        )
    )


def get_mission(session: Session, *, workspace_id: UUID, mission_id: UUID) -> MissionRow | None:
    return MissionRepository(session).get_for_workspace(workspace_id, mission_id)


def list_missions(
    session: Session, *, workspace_id: UUID, limit: int = 100, offset: int = 0
) -> list[MissionRow]:
    return MissionRepository(session).list_for_workspace(workspace_id, limit=limit, offset=offset)


def domain_mission_from_row(mission_row: MissionRow) -> DomainMission:
    return DomainMission.model_validate(mission_row.normalized_request)
