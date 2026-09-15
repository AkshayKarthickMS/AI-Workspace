"""Schema-version migration for in-flight checkpoints (ARCHITECTURE.md
section 7 item 24: "handle migration of in-flight checkpoints")."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.agents import Mission
from app.workflows.state import STATE_SCHEMA_VERSION, StateVersionError, serialize_state


def _v2_payload(mission: Mission, execution_id: object) -> dict[str, object]:
    """Shape of a Phase 3 (schema 2) checkpoint payload -- no approval,
    escalation, or qa_retry_count fields existed yet."""

    return {
        "schema_version": 2,
        "mission_id": mission.mission_id,
        "execution_id": execution_id,
        "mission": mission.model_dump(mode="json"),
        "event_limit": 25,
        "status": "running",
    }


def test_v2_checkpoint_migrates_to_current_schema() -> None:
    mission = Mission(objective="Legacy run")
    payload = _v2_payload(mission, uuid4())

    state = serialize_state(payload)

    assert state["schema_version"] == STATE_SCHEMA_VERSION
    assert state["approval"] is None
    assert state["escalation"] is None
    assert state["qa_retry_count"] == 0


def test_unknown_future_schema_version_is_rejected() -> None:
    mission = Mission(objective="From the future")
    payload = {
        "schema_version": STATE_SCHEMA_VERSION + 1,
        "mission_id": mission.mission_id,
        "execution_id": uuid4(),
        "mission": mission.model_dump(mode="json"),
        "event_limit": 25,
        "status": "running",
    }

    with pytest.raises(StateVersionError):
        serialize_state(payload)
