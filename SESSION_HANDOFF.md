# Session Handoff — AegisOS

Read this first in a new session, then `CLAUDE.md` (project orientation) and `DEVELOPER.md` (how to run it). This file exists only to carry context across a session boundary — delete it once its contents are absorbed or stale.

## Where the project stands

All 7 roadmap phases are implemented (see `CLAUDE.md`'s "Current state vs. target"). The full golden path — workspace → mission → run → plan approval → analyst → QA PASS → compliance PASS → report → artifact viewer → knowledge ingestion → audit explorer — has now been verified **live, in a real Chrome browser**, against a real FastAPI/uvicorn server, a real Next.js dev server, and a real local PostgreSQL 16 + pgvector database. The full backend test suite (`pytest`, `ruff check .`, `mypy app`) and frontend suite (`npm run lint`, `npm run typecheck`, `npm run build`) are all green.

**This session's work has NOT been committed yet.** The user asked: "First complete the project to make it work perfectly, then update the docs and commit." Docs are updated (this file, `CLAUDE.md`, `DEVELOPER.md`); the commit is the next step.

## What this session did

Continued from a prior session's handoff, which had left a `RuntimeCheckpointStore` WAL/busy_timeout fix pending and one bug (LangGraph checkpoint SQLite locking) unresolved. This session:

1. Applied that pending fix, then found it was incomplete and fixed the rest of a chain of real SQLite-concurrency bugs (detailed below).
2. Hit a wall: even after every SQLite hardening fix, a live run still reliably hit `sqlite3.OperationalError: database is locked` — reproduced with **zero concurrency** (a single curl POST, no polling at all). Systematically ruled out browser polling, file location, LangGraph's internal locking, and Windows' ProactorEventLoop before concluding real-time antivirus (Windows Defender, confirmed active via `Get-MpComputerStatus`) was intercepting writes to the SQLite file.
3. Asked the user to authorize a Defender exclusion; the harness's own auto-mode permission classifier refused to run `Add-MpPreference` even after explicit user approval (filed as product feedback).
4. Found a better fix instead of waiting on that: **`pip install pgserver`** — a Python package that bundles a real, portable PostgreSQL 16 (+ pgvector extension) binary for Windows, runnable with no Docker, no install, no admin rights. Switched the live-verification harness's main database to this real Postgres server. This completely resolved the lock issue (real Postgres has no equivalent failure mode here — one server process owns all writes, rather than many independent processes each opening the same file) and let the full golden path complete successfully on the first real attempt.
5. While verifying the UI, found and fixed one more real bug: the Plan panel showed every task frozen at "Pending" forever, even after a run completed. Fixed by exposing live per-task status over the API (see below).

## Fixes applied and verified this session (all covered by `pytest`/`ruff`/`mypy`/`npm run lint`/`npm run typecheck`/`npm run build`, all clean)

### 1. LangGraph checkpoint store WAL/busy_timeout (prior session's pending fix, now applied)

`apps/api/app/workflows/checkpoints.py`, `RuntimeCheckpointStore.__init__`: `timeout=30.0` on `sqlite3.connect`, plus `PRAGMA busy_timeout=30000` and `PRAGMA journal_mode=WAL`.

### 2. `PRAGMA journal_mode=WAL` itself needs a retry

**File:** `apps/api/app/workflows/checkpoints.py`, `_enable_wal_with_retry`.

Switching a database into WAL mode for the first time briefly needs exclusive access. A connection racing another one opening the same file for the first time can see `database is locked` on the `journal_mode` pragma itself, even with `busy_timeout` set — SQLite doesn't reliably route this one through the normal busy-handler retry path on Windows (reproduced with a small two-thread repro script). The old code's broad `except sqlite3.DatabaseError` around `__init__` was also misclassifying this transient lock as permanent `CheckpointCorruptError`. Fixed: `busy_timeout` set first, and the WAL switch itself retried up to 5 times with backoff.

### 3. `RuntimeCheckpointStore` was re-running LangGraph's setup DDL on every construction

**File:** `apps/api/app/workflows/checkpoints.py`, `_setup_once`.

LangGraph's `SqliteSaver.setup()` unconditionally re-runs `PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS ...` via `executescript()` on every call, because `is_setup` lives on the `SqliteSaver` *instance*, not the on-disk file — and a fresh instance is constructed on every API call touching a run (`build_runtime_for_workspace`, by design). Under real polling concurrency this repeated DDL churn starved a concurrent writer. Fixed: check `sqlite_master` for the `checkpoints` table first; skip `setup()` if it already exists.

### 4. The main application database engine needed the same treatment, plus `NullPool`

**File:** `apps/api/app/db/session.py`, `get_engine()`.

Same class of bug, on the app's own SQLite fallback engine (`audit_events`, `runs`, etc.) rather than the checkpoint file. SQLAlchemy's default `QueuePool` keeps several connections open concurrently across worker threads; combined with FastAPI dispatching both request handlers and `BackgroundTasks` onto the same `anyio` threadpool, this reproduced `database is locked` on plain `INSERT`s. Fixed: for a file-based (non-`:memory:`) `sqlite://` URL, use `NullPool` plus the same `busy_timeout`-then-WAL-with-retry sequence. In-memory test engines (`StaticPool`) are unaffected.

**Even with all four fixes, a live run still hit `database is locked` with zero concurrency** — see "Environment limitation" below for why, and what actually resolved it (real Postgres, not more SQLite tuning).

### 5. Plan panel frozen at "Pending" forever, even after a run completes

**Files:** `apps/api/app/api/v1/runs.py` (`RunDetailResponse` gains a `tasks` field, `_to_detail` populates it from `state.get("tasks")`), `apps/web/src/features/missions/plan-view.tsx` (`PlanView` now takes an optional `tasks` map and overlays live status onto each plan task), `apps/web/src/features/missions/run-panel.tsx` (passes `detail.tasks` through).

**Bug:** `AegisState` has two separate structures — `state["plan"]` (a frozen JSON snapshot of the `Plan` object from when the LLM drafted it; each task's `status` field is `pending` forever, since this snapshot is never rewritten) and `state["tasks"]` (a `dict[task_id, JsonObject]` that *is* live-updated as each task actually runs, completes, fails, or retries). `RunDetailResponse` only ever returned `plan`, never `tasks`, so the frontend had no way to show real per-task progress — confirmed live in the browser: a fully completed run (QA PASS, Compliance PASS, report generated) still showed all four plan tasks as "Pending". Fixed by exposing `tasks` over the API and having `PlanView` prefer the live status when present. OpenAPI schema and generated TS types (`packages/shared/openapi.json`, `packages/shared/src/api-types.ts`) were regenerated and are part of this session's changes — `tests/test_openapi_contract.py` passes.

## Environment limitation encountered, and how it was actually resolved

After fixes #1-4, a live run **still** hit `sqlite3.OperationalError: database is locked` — reproduced with a single curl `POST` and zero follow-up requests of any kind (no browser, no polling). Ruled out, in order:

1. Browser polling concurrency (reproduces identically with zero concurrent requests).
2. Checkpoint/database file location (moving files to a scratch temp directory made no difference).
3. LangGraph's internal `threading.Lock` in `SqliteSaver.cursor()` (read its source: fully released within one `with` block, no leakage).
4. Windows' default `ProactorEventLoop` vs `SelectorEventLoop` for asyncio (switched explicitly, no difference).

`Get-MpComputerStatus` confirmed Windows Defender real-time protection is active. Real-time AV scanning intercepting a SQLite file mid-write is a well-documented cause of exactly this symptom on Windows. Asked the user, who approved a scoped Defender exclusion; **the harness's own auto-mode permission classifier refused to run `Add-MpPreference` even after that explicit approval** (tagged `[Security Weaken]`, no override path) — filed as product feedback.

**What actually fixed it:** `pip install pgserver` (into `apps/api/.venv`; not added to `pyproject.toml` — a local scratch convenience, not a project dependency) provides a real, portable PostgreSQL 16 + pgvector Windows binary, startable with `pgserver.get_server(<data dir>)` and no Docker, no system install, no admin rights. Switching the live-verification harness's `AEGIS_DATABASE_URL` to this real Postgres server (keeping the LangGraph checkpoint store as SQLite, per its real architectural design, but now under far lighter write load since the high-frequency `audit_events` writes go to Postgres instead) resolved the issue completely — the golden path completed successfully on the first attempt afterward, no further lock errors of any kind.

**Practical implication:** this doesn't mean fixes #1-4 were wasted — they're real, correct hardening of the documented SQLite *test* fallback (AGENTS.md) against genuine multi-connection contention, verified via a standalone concurrency repro (one thread running `AegisRuntime.run()` while another hammers `get_state()` every 100ms — passed cleanly across many repeated runs) independent of the AV issue. But they could not, and were never going to, fully solve a live-server SQLite workload on a machine with active real-time AV scanning — that specific combination needs either a Defender exclusion (user must add manually; see below) or a real database server (Postgres), which is what the project's own architecture already specifies for anything beyond automated tests.

## Reproducing the live-browser verification (throwaway harness, not committed)

The harness lives at (session-specific, will not persist) `<scratchpad>/smoke/live_backend.py`. To rebuild it:

1. `pip install pgserver fakeredis` into `apps/api/.venv`.
2. At the top of the script, before importing `app.main`: start `pgserver.get_server(<data dir>)`, set `AEGIS_DATABASE_URL` to its URI with the scheme rewritten from `postgresql://` to `postgresql+psycopg://`, then `alembic upgrade head` against it (this also exercises `CREATE EXTENSION IF NOT EXISTS vector`, confirmed working in this pgserver build).
3. Build one shared `fakeredis.FakeServer()`; monkeypatch `redis.Redis.from_url` and `app.api.v1.runs.aioredis.from_url` to return `FakeStrictRedis`/`FakeRedis` instances bound to it. **Do not** try a real `fakeredis.TcpFakeServer` or anything binding a new listening TCP port — that hangs forever in this sandbox, reproduced twice, looks like a firewall-prompt equivalent that never resolves headlessly.
4. Monkeypatch `app.services.runs.build_runtime_for_workspace` to build an `AegisRuntime` with `FakeLLMProvider`/`FakeEmbeddingProvider` (only `DraftPlan` and `_Critique` response models are ever requested — grep-verified across `orchestrator.py`/`qa.py`) and a scripted "analyst" task (`input={"dataset_path": <absolute path to data/demo/sales_data.csv>}`).
5. Also monkeypatch `app.api.v1.knowledge.ingest_document` (bound name, not `app.services.knowledge.ingest_document`) to default `embeddings=FakeEmbeddingProvider()` — knowledge ingestion is a *separate* dependency path from the runtime factory and otherwise tries to reach a real Ollama at `localhost:11434`.
6. `uvicorn.run(app, host="127.0.0.1", port=8000)` — `127.0.0.1` specifically; `http://localhost:8000` intermittently resolved to `::1` first on this Windows machine with nothing listening there.
7. Frontend: `npm run dev --workspace=@aegisos/web -- -p 3010` with `API_INTERNAL_URL=http://127.0.0.1:8000` — port 3010, not 3000, because an unrelated pre-existing Vite dev server for a different project on this machine (`C:\Users\AkshayKarthickMS\GeoFencing\Hand-Gesture-Recognition`) is bound to `::1:3000`, and Chrome's `localhost` resolution hit that instead. Check `Get-NetTCPConnection -LocalPort 3000` for this kind of collision before assuming a fresh `next dev` "just works" on this machine.
8. Drive it with the `claude-in-chrome` MCP tools. A freshly-rendered button's first click sometimes doesn't register (observed repeatedly, cause unconfirmed — possibly a hydration-timing race) — always screenshot after a click that was supposed to navigate/submit, and click again if nothing changed, rather than assuming the click failed for a different reason.

## Suggested next steps, in order

1. This handoff assumes the commit the user asked for has just happened (or is about to) — check `git log` if picking this up fresh to confirm.
2. If repeatable, CI-friendly integration testing against real Postgres/pgvector matters (Phase 7 item 39, still not done — see `CLAUDE.md`'s known-gaps list): `pgserver` is a genuinely good candidate for this, since it needs no Docker and starts in-process in under a second. Worth prototyping a pytest fixture around it.
3. Redis and Ollama remain unexercised live in this dev environment (only Postgres got a real-server upgrade this session). If either becomes available (or another `pgserver`-style portable binary exists for one of them), the same substitution pattern in the harness above would extend easily.
4. Continue watching for the same class of bug elsewhere: anywhere code assumes "only one connection/thread touches this SQLite file at a time" is worth a second look if the SQLite fallback path is ever exercised for more than a quick automated test — this class of bug has now bitten twice across two sessions.
