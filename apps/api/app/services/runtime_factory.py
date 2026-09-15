"""Constructs an ``AegisRuntime`` wired for the API layer (ARCHITECTURE.md
section 6). Kept separate from ``AegisRuntime.__init__``'s own defaults so
call sites (routes, background tasks, tests) share one place that decides
how production runs are wired -- e.g. the Postgres+Redis composite audit
sink -- without hand-assembling it at every call site.

Retrieval (``search=``) is deliberately left unwired here: ``HybridSearchService``
is bound to one ``Session`` at construction time, but a run backed by this
factory can pause for an indefinite human-approval wait, and holding a DB
session open across that wait is exactly the kind of connection-pool leak
AGENTS.md's persistence rules exist to prevent. Wiring retrieval per-call
(a session-factory-based redesign of ``HybridSearchService``, mirroring how
``TextToSqlTool`` already takes a session *factory*) is left for later --
until then, Research falls back to its static-sources-only behavior here,
which is a real, working mode, not a stub.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import redis

from app.core.config import get_settings
from app.events.audit import CompositeAuditSink, PostgresAuditSink
from app.events.redis_bus import RedisEventBusSink
from app.workflows.runtime import AegisRuntime


def build_runtime_for_workspace(workspace_id: UUID) -> AegisRuntime:
    settings = get_settings()
    data_root = Path(settings.data_root).resolve()
    redis_client = redis.Redis.from_url(settings.redis_url)
    audit = CompositeAuditSink([PostgresAuditSink(), RedisEventBusSink(redis_client)])
    return AegisRuntime(data_root=data_root, audit=audit, workspace_id=workspace_id)
