"""Shared secret-redaction helper (AGENTS.md: redact before logs, events,
model context, sandbox output, and artifacts)."""

from __future__ import annotations

import re

_SENSITIVE_VALUE = re.compile(r"(?i)((?:api[_-]?key|password|secret|token)\s*[=:]\s*)\S+")


def redact(text: str) -> str:
    """Replace obvious secret-shaped values (``key=...``, ``token: ...``) with
    a fixed marker. Best-effort, not a substitute for not logging secrets."""

    return _SENSITIVE_VALUE.sub(r"\1[REDACTED]", text)
