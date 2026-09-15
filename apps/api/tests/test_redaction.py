"""Unit coverage for the shared secret-redaction helper (AGENTS.md: redact
before logs, events, model context, sandbox output, and artifacts). Sandbox
output redaction is already covered end-to-end in test_code_execution.py;
this exercises the helper directly."""

from __future__ import annotations

import pytest

from app.core.redaction import redact


@pytest.mark.parametrize(
    "raw",
    [
        "api_key=sk-abc123XYZ",
        "API-KEY: sk-abc123XYZ",
        "password=hunter2",
        "secret: s3cr3t-value",
        "token=eyJhbGciOiJIUzI1NiJ9",
    ],
)
def test_redact_masks_sensitive_key_value_pairs(raw: str) -> None:
    result = redact(raw)
    assert "[REDACTED]" in result
    assert "sk-abc123XYZ" not in result
    assert "hunter2" not in result
    assert "s3cr3t-value" not in result
    assert "eyJhbGciOiJIUzI1NiJ9" not in result


def test_redact_preserves_unrelated_text() -> None:
    text = "Revenue grew 12% in Q3, driven by the EMEA region."
    assert redact(text) == text


def test_redact_masks_only_the_value_not_the_key() -> None:
    result = redact("Config: api_key=abc123 loaded successfully")
    assert result.startswith("Config: api_key=[REDACTED]")
    assert "loaded successfully" in result
