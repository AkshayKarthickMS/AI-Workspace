"""Local checkpoint abstraction backed by LangGraph's SQLite saver."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver


class CheckpointError(RuntimeError):
    """Raised when checkpoint access or persistence cannot be completed safely."""


class CheckpointNotFoundError(CheckpointError):
    """Raised when an execution has no checkpoint to resume."""


class CheckpointCorruptError(CheckpointError):
    """Raised when local checkpoint storage cannot be read as valid SQLite data."""


class RuntimeCheckpointStore:
    """Own the local durable LangGraph checkpointer for a runtime instance.

    SQLite transactions provide atomic checkpoint writes. This adapter intentionally
    exposes LangGraph's saver rather than duplicating graph checkpoint persistence;
    PostgreSQL can replace this class without changing runtime orchestration.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None
        try:
            self._connection = sqlite3.connect(
                self.path, check_same_thread=False, timeout=30.0
            )
            # busy_timeout first so it's already in effect if the WAL switch
            # below has to wait; a bare CheckpointError re-raised here (not
            # DatabaseError) so the outer except doesn't mistake a lock for
            # corruption.
            self._connection.execute("PRAGMA busy_timeout=30000")
            self._enable_wal_with_retry()
            self.saver = SqliteSaver(self._connection)
            self._setup_once()
        except sqlite3.DatabaseError as exc:
            self.close()
            raise CheckpointCorruptError(
                "Checkpoint storage is not a valid SQLite database"
            ) from exc

    def _enable_wal_with_retry(self) -> None:
        """Switching a database into WAL mode for the first time briefly
        needs exclusive access, so a connection racing another one that's
        also opening this same file for the first time (e.g. a background
        task and a concurrent API request both constructing a
        ``RuntimeCheckpointStore`` for the same run -- ``runtime_factory.py``
        builds a fresh one per call) can see ``database is locked`` even
        though ``busy_timeout`` is set: SQLite does not route this
        particular pragma through the normal busy-handler retry path on
        every platform (reproduced empirically on Windows). Retried here so
        that transient lock is not mistaken by the caller for a corrupt
        database file.
        """

        assert self._connection is not None
        attempts = 5
        for attempt in range(attempts):
            try:
                self._connection.execute("PRAGMA journal_mode=WAL")
                return
            except sqlite3.OperationalError:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))

    def _setup_once(self) -> None:
        """Skip ``SqliteSaver.setup()`` when the schema already exists.

        ``setup()`` unconditionally re-runs ``PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS ...`` via ``executescript()`` because
        ``is_setup`` lives on the ``SqliteSaver`` instance, not the on-disk
        file -- and a fresh ``RuntimeCheckpointStore``/``SqliteSaver`` is
        constructed on *every* API call that touches a run
        (``runtime_factory.build_runtime_for_workspace``, by design -- see
        CLAUDE.md's known perf-inefficiency note). Under real polling
        concurrency (the frontend's run-status GET every few seconds while a
        background task is mid-write) that repeated DDL churn against the
        same file reliably starved the writer on Windows SQLite, observed
        empirically as `GET .../runs/{id}` 404ing indefinitely because the
        background task's first checkpoint write never completed. The
        schema is only ever created once per file, so checking for it first
        is sufficient and avoids re-issuing that DDL on every read.
        """

        assert self._connection is not None
        exists = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        ).fetchone()
        if exists is not None:
            self.saver.is_setup = True
        else:
            self.saver.setup()

    @staticmethod
    def config(execution_id: UUID) -> RunnableConfig:
        return {"configurable": {"thread_id": str(execution_id)}}

    def has_execution(self, execution_id: UUID) -> bool:
        try:
            return self.saver.get_tuple(self.config(execution_id)) is not None
        except sqlite3.DatabaseError as exc:
            raise CheckpointCorruptError("Checkpoint storage could not be read") from exc

    def checkpoint_count(self, execution_id: UUID) -> int:
        """Return the stored checkpoint count for diagnostics and deterministic tests."""

        try:
            count = 0
            for _ in self.saver.list(self.config(execution_id)):
                count += 1
            return count
        except sqlite3.DatabaseError as exc:
            raise CheckpointCorruptError("Checkpoint storage could not be read") from exc

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> RuntimeCheckpointStore:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
