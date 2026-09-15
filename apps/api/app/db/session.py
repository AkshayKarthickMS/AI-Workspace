"""SQLAlchemy engine and session factory for the PostgreSQL persistence layer."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite") and ":memory:" not in settings.database_url:
        # QueuePool (SQLAlchemy's default) keeps several sqlite3 connections
        # open concurrently and hands them across worker threads over their
        # lifetime; combined with FastAPI dispatching both request handlers
        # and BackgroundTasks onto the same anyio threadpool, that reliably
        # produced multi-second to 30s+ writer starvation on
        # `sqlite3.OperationalError: database is locked` in real (non-test)
        # use, reproduced empirically under a real uvicorn server with real
        # browser polling. SQLite does its own file-level locking, so a real
        # connection pool buys nothing here -- NullPool (one physical
        # connection per checkout, closed immediately after) avoids the
        # long-lived-connection contention entirely. The in-memory test
        # engines (StaticPool, one shared connection) are unaffected.
        engine_kwargs["poolclass"] = NullPool
    engine = create_engine(settings.database_url, **engine_kwargs)
    if engine.dialect.name == "sqlite":
        # See app/workflows/checkpoints.py's near-identical fix for why the
        # WAL switch itself needs a retry, not just a busy_timeout.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA busy_timeout=30000")
            attempts = 5
            for attempt in range(attempts):
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError:
                    if attempt == attempts - 1:
                        raise
                    time.sleep(0.1 * (attempt + 1))
            cursor.close()

    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a transactional session: commits on success, rolls back on error.

    A FastAPI request-scoped dependency is Phase 5 work once routes exist to
    hang it from; this is the synchronous building block that will use.
    """

    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
