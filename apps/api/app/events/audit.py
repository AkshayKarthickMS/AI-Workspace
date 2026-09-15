import json
import logging
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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


class PostgresAuditSink(AuditSink):
    """Durable audit sink backed by the ``audit_events`` table.

    Keeps the base class's in-memory list and structured log line (useful for
    tests and for correlating with request logs) and additionally persists
    every event. Each ``emit()`` commits its own transaction rather than
    joining a wider unit of work — there is no request/service-layer
    transaction boundary yet for it to join (that lands with Phase 5's API
    routes); revisit this once one exists.
    """

    def __init__(
        self,
        session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
        on_event: Callable[[AuditEvent], None] | None = None,
    ) -> None:
        super().__init__(on_event)
        if session_factory is None:
            # Imported lazily so importing this module never requires
            # app.db/app.core.config unless a PostgresAuditSink is actually built.
            from app.db.session import session_scope

            session_factory = session_scope
        self._session_scope = session_factory

    def emit(self, event: AuditEvent) -> AuditEvent:
        super().emit(event)
        # Imported lazily so importing this module never requires app.models
        # (and its SQLAlchemy/pgvector dependencies) unless this sink is used.
        from app.models.audit import AuditEventRecord

        with self._session_scope() as session:
            session.add(
                AuditEventRecord(
                    id=event.event_id,
                    event_type=event.event_type,
                    actor=event.actor,
                    mission_id=event.mission_id,
                    run_id=event.run_id,
                    task_id=event.task_id,
                    status=event.status,
                    occurred_at=event.timestamp,
                    event_metadata=event.metadata,
                )
            )
        return event


class CompositeAuditSink(AuditSink):
    """Fans one ``emit()`` out to several child sinks (e.g. Postgres + Redis).

    Keeps its own in-memory ``events`` list and ``on_event`` hook (so
    ``runtime.audit.events`` still works as the single place to look), but
    does not also call the base class's log line — each child sink already
    logs once on its own ``emit()``, so a plain ``AuditSink.emit()`` here
    would just duplicate that line per child without adding information.
    """

    def __init__(
        self, sinks: Iterable[AuditSink], on_event: Callable[[AuditEvent], None] | None = None
    ) -> None:
        super().__init__(on_event)
        self._sinks = list(sinks)

    def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        if self._on_event:
            self._on_event(event)
        for sink in self._sinks:
            sink.emit(event)
        return event
