"""Text-to-SQL execution tool (ARCHITECTURE.md section 10). Every statement is
validated as read-only SELECT-only (app.tools.sql_safety) before it ever
reaches the database; row and time limits are enforced here."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.data_queries import DataQueryResult
from app.tools.sql_safety import validate_select_only


class SqlExecutionError(RuntimeError):
    """Raised when an already-validated statement still fails to execute
    (unknown table/column, permission denied, etc.)."""


class TextToSqlTool:
    def __init__(
        self,
        session_factory: Callable[[], AbstractContextManager[Session]],
        *,
        row_limit: int = 200,
        timeout_seconds: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self.row_limit = row_limit
        self.timeout_seconds = timeout_seconds

    def execute(self, statement: str) -> DataQueryResult:
        validate_select_only(statement)

        start = time.monotonic()
        with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                session.execute(
                    text("SET LOCAL statement_timeout = :ms"),
                    {"ms": self.timeout_seconds * 1000},
                )
            try:
                cursor_result = session.execute(text(statement))
            except Exception as exc:
                raise SqlExecutionError(f"Query execution failed: {exc}") from exc
            columns = list(cursor_result.keys())
            rows = cursor_result.fetchmany(self.row_limit)

        duration_ms = int((time.monotonic() - start) * 1000)
        return DataQueryResult(
            statement=statement,
            columns=columns,
            row_count=len(rows),
            rows=[
                {column: _coerce_cell(value) for column, value in zip(columns, row, strict=True)}
                for row in rows
            ],
            duration_ms=duration_ms,
            evidence=[],
        )


def _coerce_cell(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
