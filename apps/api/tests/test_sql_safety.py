"""Adversarial coverage for the Data agent's SELECT-only statement validator
(AGENTS.md: reject any non-SELECT statement before execution, not merely log it)."""

import pytest

from app.tools.sql_safety import SqlValidationError, validate_select_only

VALID_STATEMENTS = [
    "SELECT 1",
    "  select * from missions  ",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "SELECT * FROM t WHERE x = 'a; DROP TABLE t'",
    "SELECT 1;",
]

INVALID_STATEMENTS = [
    "",
    "   ",
    "SELECT * FROM t; DROP TABLE t",
    "SELECT 1; SELECT 2",
    "DROP TABLE t",
    "DELETE FROM t",
    "UPDATE t SET x=1",
    "INSERT INTO t VALUES (1)",
    "SELECT * INTO new_table FROM t",
    "CREATE TABLE t (id int)",
    "TRUNCATE t",
    "GRANT ALL ON t TO public",
]


@pytest.mark.parametrize("statement", VALID_STATEMENTS)
def test_accepts_read_only_select_statements(statement: str) -> None:
    validate_select_only(statement)  # must not raise


@pytest.mark.parametrize("statement", INVALID_STATEMENTS)
def test_rejects_unsafe_or_malformed_statements(statement: str) -> None:
    with pytest.raises(SqlValidationError):
        validate_select_only(statement)
