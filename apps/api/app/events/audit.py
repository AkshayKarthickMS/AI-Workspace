import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEvent(BaseModel):
    """Append-only record of an agent invocation or workflow transition."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    actor: str
    mission_id: UUID
    run_id: UUID
    task_id: UUID | None = None
    status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AuditSink:
    """Small in-process sink; persistence can be added behind this interface."""

    def __init__(self, on_event: Callable[[AuditEvent], None] | None = None) -> None:
        self.events: list[AuditEvent] = []
        self._on_event = on_event

    def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        if self._on_event:
            self._on_event(event)
        logger.info("audit_event %s", json.dumps(event.model_dump(mode="json"), sort_keys=True))
        return event
