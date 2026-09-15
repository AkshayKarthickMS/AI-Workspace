"""Contract test: the committed ``packages/shared/openapi.json`` (the input
to the frontend's generated TypeScript client) must match what the live
FastAPI app actually serves. If this fails, a route/schema changed without
regenerating the frontend types -- see CLAUDE.md's "Regenerate packages/
shared's TS types" command."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

SHARED_OPENAPI_PATH = Path(__file__).parents[3] / "packages" / "shared" / "openapi.json"


def test_committed_openapi_schema_matches_the_live_app() -> None:
    committed = json.loads(SHARED_OPENAPI_PATH.read_text(encoding="utf-8"))
    live = app.openapi()
    assert committed == live, (
        "packages/shared/openapi.json is stale. Regenerate it: "
        "python apps/api/scripts/export_openapi.py && npm run generate:api-types"
    )
