"""SQL statement safety validation for the Data agent's text-to-SQL tool.

AGENTS.md: any generated statement that is not a ``SELECT`` must be rejected
before execution, not merely logged. This is the enforcement point; the Data
agent must run every LLM-proposed statement through it before execution.
"""

from __future__ import annotations

import sqlparse

_BANNED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "UPSERT",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "ATTACH",
    "DETACH",
    "VACUUM",
    "REINDEX",
    "COPY",
    "CALL",
    "EXECUTE",
    "INTO",  # blocks SELECT ... INTO table
}


class SqlValidationError(ValueError):
    """Raised when a proposed SQL statement is not a single, read-only SELECT."""


def validate_select_only(statement: str) -> None:
    """Raise ``SqlValidationError`` unless ``statement`` is exactly one
    read-only ``SELECT`` (a leading ``WITH`` CTE is allowed), with no other
    statement chained after it."""

    stripped = statement.strip()
    if not stripped:
        raise SqlValidationError("Empty SQL statement")

    statements = [
        parsed
        for parsed in sqlparse.parse(stripped)
        if parsed.token_first(skip_cm=True) is not None
    ]
    if len(statements) != 1:
        raise SqlValidationError("Exactly one SQL statement is allowed")

    stmt = statements[0]
    first_token = stmt.token_first(skip_cm=True)
    first_keyword = first_token.normalized.upper() if first_token else ""
    if first_keyword not in {"SELECT", "WITH"}:
        raise SqlValidationError(
            f"Statement must start with SELECT or WITH, got {first_keyword!r}"
        )

    for token in stmt.flatten():
        if not token.ttype:
            continue
        normalized = token.normalized.upper()
        if normalized in _BANNED_KEYWORDS:
            raise SqlValidationError(f"Disallowed keyword in statement: {normalized}")

    statement_type = stmt.get_type()
    if statement_type not in {"SELECT", "UNKNOWN"}:
        raise SqlValidationError(f"Only SELECT statements are allowed, got {statement_type}")
