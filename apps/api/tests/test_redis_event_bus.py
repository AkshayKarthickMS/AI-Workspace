"""Redis Stream event bus tests, using a mocked Redis client -- no live
Redis server required (AGENTS.md). Validates that every audit event is
published to the correct per-run stream and that CompositeAuditSink fans out
to multiple child sinks without duplicating the base log line per child."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

from app.events.audit import AuditEvent, AuditSink, CompositeAuditSink
from app.events.redis_bus import RedisEventBusSink, run_event_stream_key


def _event() -> AuditEvent:
    return AuditEvent(
        event_type="task.completed",
        actor="analyst",
        mission_id=uuid4(),
        run_id=uuid4(),
        status="completed",
    )


def test_redis_event_bus_publishes_to_the_correct_stream() -> None:
    client = MagicMock()
    sink = RedisEventBusSink(client)
    event = _event()

    sink.emit(event)

    assert sink.events == [event]
    client.xadd.assert_called_once()
    (stream_key, fields), kwargs = client.xadd.call_args
    assert stream_key == run_event_stream_key(event.run_id)
    assert json.loads(fields["payload"])["event_type"] == "task.completed"
    assert kwargs["maxlen"] == 1000
    assert kwargs["approximate"] is True


def test_composite_audit_sink_fans_out_to_every_child() -> None:
    redis_client = MagicMock()
    redis_sink = RedisEventBusSink(redis_client)
    postgres_like_sink = AuditSink()
    composite = CompositeAuditSink([redis_sink, postgres_like_sink])
    event = _event()

    composite.emit(event)

    assert composite.events == [event]
    assert redis_sink.events == [event]
    assert postgres_like_sink.events == [event]
    redis_client.xadd.assert_called_once()
