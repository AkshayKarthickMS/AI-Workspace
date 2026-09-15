"""Redis Stream-backed event bus: publishes every audit event for SSE
fan-out and cross-agent notification (ARCHITECTURE.md section 7 "Agent
communication", section 11).

This is a notification channel only. Delegation between agents still always
re-enters the graph through the orchestrator/dispatch node (AGENTS.md) --
nothing here lets one agent invoke another's tools directly, and nothing in
this runtime subscribes to its own stream to drive decisions. A Stream
(rather than plain Pub/Sub) is used specifically so a client that
reconnects mid-run can replay missed events instead of losing them, per
ARCHITECTURE.md section 11 ("reconnecting clients can recover from the API").
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.events.audit import AuditEvent, AuditSink

logger = logging.getLogger(__name__)
STREAM_MAXLEN = 1000


def run_event_stream_key(run_id: UUID) -> str:
    return f"aegisos:run-events:{run_id}"


class RedisEventBusSink(AuditSink):
    """Durable-enough fan-out sink. Keeps the base class's in-memory list and
    structured log line (useful standalone and in tests) and additionally
    publishes every event to a per-run Redis Stream.
    """

    def __init__(
        self, redis_client: Any, on_event: Callable[[AuditEvent], None] | None = None
    ) -> None:
        super().__init__(on_event)
        self._redis = redis_client

    def emit(self, event: AuditEvent) -> AuditEvent:
        super().emit(event)
        try:
            self._redis.xadd(
                run_event_stream_key(event.run_id),
                {"payload": event.model_dump_json()},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        except Exception:
            # Observability must never take the mission down with it -- SSE
            # fan-out degrades to "not live right now", not a failed run.
            logger.warning("redis_event_publish_failed run_id=%s", event.run_id, exc_info=True)
        return event
