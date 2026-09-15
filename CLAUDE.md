# CLAUDE.md

Session orientation for AegisOS. This file is intentionally short — it points to the documents that govern scope and rules rather than restating them, and it exists so a new session doesn't assume more is built than actually is.

## Read in this order

1. `requirements.md` — product vision and scope, source of truth for intent.
2. `ARCHITECTURE.md` — the target system design derived from it (agent roster, data model, API surface, security model).
3. `AGENTS.md` — binding development rules (technology boundaries, safety rules, quality gate). Follow these on every change.

## Current state vs. target — read this before assuming anything exists

`ARCHITECTURE.md` describes the target system. All 7 roadmap phases have landed. As of the last audit:

- **Implemented:**
  - **Persistence** (`apps/api/app/models/`, `db/`): all 16 tables from ARCHITECTURE.md §8 as SQLAlchemy models, one Alembic migration (`alembic/versions/`), a workspace-scoped repository per table (`db/repositories/`). Cross-dialect: real pgvector/JSONB on PostgreSQL, a SQLite-compatible fallback for tests. No Docker in this dev environment, but the migration (including `CREATE EXTENSION IF NOT EXISTS vector`) and the full golden path have now been verified against a *real* local PostgreSQL 16 + pgvector server via the `pgserver` package (a genuine `postgres.exe`, no Docker needed — `pip install pgserver` into a venv, `pgserver.get_server(<data dir>)`) — see `SESSION_HANDOFF.md` for why this was worth doing (a plain SQLite substitute for the main app DB reliably hit `sqlite3.OperationalError: database is locked` under real (non-`TestClient`) concurrency in this sandbox, very likely Windows Defender real-time scanning a frequently-written file; real Postgres sidesteps that class of problem entirely since all writes go through one server process). `pgserver` is a local scratch convenience, not added to `pyproject.toml` — `docker compose up` (Option A in `DEVELOPER.md`) remains the documented, supported way to run a real Postgres for this project.
  - **LLM provider layer** (`apps/api/app/llm/`): `OllamaProvider`/`HuggingFaceProvider` (structured-output-only, retry-with-repair), `FakeLLMProvider` for tests, and `LangfuseTracingProvider` (wraps any provider, correlates every call to run_id/task_id) — selected/composed via `build_traced_llm_provider`. `AEGIS_MODEL_PROVIDER` picks Ollama vs Hugging Face; tracing auto-enables only when both Langfuse keys are set.
  - **Agent roster** (`apps/api/app/agents/`): the full 7-role set — Orchestrator (LLM-driven planning), Research, Data (text-to-SQL), Analyst (generalized tabular analysis + sandboxed code execution), QA (embedding groundedness + LLM self-critique), Compliance (deterministic PII/policy scan), Report (requires both QA PASS and Compliance PASS, emits a `SlideDeck`). `DataAnalystAgent`/`VerificationAgent`/`PandasSalesAnalysisTool` are deleted, not deprecated-in-place.
  - **Retrieval** (`apps/api/app/retrieval/`): `KnowledgeIngestionService` (LlamaIndex chunking) and `HybridSearchService` (pgvector cosine distance on Postgres, Python fallback elsewhere), wired into `ControlledResearchTool` as an *optional* extra source.
  - **Sandboxed code execution** (`apps/api/app/tools/code_execution.py`): Docker-based (network-disabled, non-root, resource/time-bounded, ephemeral scratch dir) — validated by mocking the Docker client (config asserted correct), not a real container run; no live Docker daemon in this dev environment.
  - **Workflow orchestration** (`apps/api/app/workflows/runtime.py`, `state.py`): the full graph shape — `plan -> await_approval -> dispatch -> {research|data|analyst} -> dispatch -> qa -> (retry|replan->await_approval|compliance) -> compliance -> (escalate_approval|report) -> report -> dispatch(finalize)`. Every run now pauses at `await_approval` before any task executes; `AegisRuntime.approve_plan`/`reject_plan`/`resolve_escalation` resolve the two human-in-the-loop gates (call `resume()` afterward to continue — these methods only record the decision). QA failures get one bounded retry of the gathering phase, then require re-approval (full automatic re-planning via a second LLM call is explicitly out of scope — a human re-approving the same plan is the safety valve). `AegisState`/`RuntimeStateRecord` schema is version 3 (adds `approval`, `escalation`, `qa_retry_count`; `serialize_state` auto-migrates a v2 payload). The interrupt/resume mechanics (self-loop back to the same node while a decision is pending; `update_state()` recomputing pending conditional routing without re-running the node) were verified empirically against real langgraph with a throwaway script before being relied on (not committed) — worth re-verifying the same way after any langgraph version upgrade. `RuntimeCheckpointStore` (`checkpoints.py`) sets `busy_timeout`, retries the one-time WAL-mode switch, and skips LangGraph's `SqliteSaver.setup()` DDL once the schema already exists on disk — all three needed to keep a file-based SQLite checkpoint store from deadlocking/starving under real (non-`TestClient`) concurrent access, per-connection-per-call as `build_runtime_for_workspace` already does; see `SESSION_HANDOFF.md` for how this was diagnosed if it needs re-verifying.
  - **Event bus** (`apps/api/app/events/`): `RedisEventBusSink` publishes every audit event to a per-run Redis Stream, tailed by the SSE endpoint below; `CompositeAuditSink` fans one `emit()` out to multiple sinks (Postgres + Redis in the API's runtime factory). `RedisEventBusSink.emit()` degrades gracefully (logs a warning) if Redis is unreachable — a run never fails because observability did.
  - **HTTP API** (`apps/api/app/api/v1/`, `app/services/`): the full route surface from ARCHITECTURE.md §9 — workspaces (bootstrap), missions, runs (start/detail/approvals/resume/cancel/SSE), artifacts, audit events, knowledge documents. Auth is the documented local-dev identity-header mode (§12), with workspace-scoped RBAC (`app/api/deps.py`) enforced on every route via `require_workspace_role`. Starting a run returns immediately (202) and executes via `BackgroundTasks`, which is how ARCHITECTURE.md §6 says Day-1 should work; `GET .../runs/{run_id}` reads live state straight from the LangGraph checkpoint (`AegisRuntime.get_state`) rather than a separately-synced Postgres projection, which is instead a best-effort listing/history projection kept in sync opportunistically after each background step. A completed run's `FinalReport` is written to a local-file artifact store (`AEGIS_ARTIFACT_ROOT`) and recorded in `artifacts`. `RunDetailResponse` also exposes `tasks` (`AegisState["tasks"]`, live per-task status keyed by task_id) alongside `plan` (the frozen initial-plan snapshot, whose own per-task `status` never advances past `pending` since it's never rewritten during execution) — the frontend's `PlanView` merges the two so the UI shows real per-task progress instead of a permanently-stale plan.
  - **API → TypeScript types** (`packages/shared/`): `apps/api/scripts/export_openapi.py` dumps the live OpenAPI schema to `packages/shared/openapi.json`; `npm run generate:api-types` (root) runs `openapi-typescript` over it into `packages/shared/src/api-types.ts`, which `src/index.ts` re-exports named types from (including `HealthResponse`, now derived rather than hand-written). Both generated files are committed; regenerate and commit again after any route/schema change.
  - **Frontend** (`apps/web/src/`): a full client on top of the v1 API — `lib/api-client.ts` (typed fetch wrapper reading the local-dev identity header from `lib/identity.ts`; `streamRunEvents` consumes SSE via `fetch`+`ReadableStream` since `EventSource` can't send custom headers), `features/identity/` and `features/workspace/` (React context providers, localStorage-backed), hand-written Tailwind primitives in `components/ui/` (no shadcn — `components.json` exists but was never bootstrapped, and hand-rolled classes already matched the existing dark slate/cyan theme). Screens: dashboard (`app/page.tsx`, identity/workspace onboarding + mission list), mission creation (`app/missions/new/`), mission detail (`app/missions/[missionId]/` — plan, run history, live SSE timeline, plan-approval/escalation decisions via `features/missions/approval-panel.tsx`, artifact viewer/download), knowledge base (`app/knowledge/`), audit explorer (`app/audit/`). Two small backend additions were needed to support this: `GET .../missions/{id}/runs` (run history list) and `GET .../artifacts/{id}/content` (serves a `file://` artifact's bytes, since the browser can't fetch that URI directly); `RunDetailResponse` also gained a `plan` field and `MissionResponse` a `raw_request` field, both previously computed but not exposed over HTTP.
- **Known gaps to watch:**
  - The full golden path (workspace → mission → run → plan approval → analyst → QA PASS → compliance PASS → report → artifact viewer → knowledge ingestion → audit explorer) has now been verified live, in a real Chrome browser, against a real FastAPI/uvicorn server, a real Next.js dev server, and a real local PostgreSQL 16 + pgvector database (see the Persistence bullet above) — this is the first session to get past a live SQLite substitute's Windows-specific lock contention. Ollama, Redis, and Docker are still substituted even in that verification (`FakeLLMProvider`/`FakeEmbeddingProvider`, in-process `fakeredis`, and no code-execution task in the scripted plan respectively) — none of those three has been exercised live in this dev environment. `tests/test_api_runs.py`'s full mission→run→approval→completion HTTP flow remains the automated-test equivalent (SQLite + fakes, per AGENTS.md).
  - Retrieval (`HybridSearchService`) is deliberately not wired into the API's runtime factory (`app/services/runtime_factory.py`) — it's bound to one DB session at construction time, and a run can pause indefinitely for approval, so holding a session open across that wait would leak connections. Research falls back to static-sources-only. Fixing this means giving `HybridSearchService` a session-factory-based redesign (mirroring `TextToSqlTool`), not yet done.
  - Constructing an `AegisRuntime` (e.g. just to read status via `GET .../runs/{run_id}`) builds every agent/tool even though only the checkpoint is needed — a known perf inefficiency, not a functional problem, from not having split "graph+checkpoint access" out of full agent wiring.
  - `RunHistory`'s "a run is already in progress" check is based on the run list as of its last fetch/refresh, not a live subscription — it can be briefly stale if a run is started from elsewhere.
  - No *automated* test runs against real Postgres/pgvector/Redis/Ollama/Docker (Phase 7 item 39, disposable-Postgres integration tests, was skipped — no Docker in this dev environment to build or run them against in CI). The live-browser verification above used a real Postgres, but manually, not as a repeatable automated test; `DEVELOPER.md` documents the manual `docker compose up` + click-through as the substitute until an automated version exists.
- **Tests & quality gates** (Phase 7): added `tests/test_redaction.py` (direct unit coverage of the redaction helper), a cancellation test in `tests/test_api_runs.py`, and `tests/test_openapi_contract.py` (fails if `packages/shared/openapi.json` drifts from the live app schema). Everything else in the Phase 7 checklist (agent/tool/repository unit tests, workflow retry/replan/escalation tests, SQL/sandbox safety tests, the authorization matrix) was already covered by Phases 2-5's own test suites — see `DEVELOPER.md` §6 for the full map of what's tested where. Added `.github/workflows/ci.yml` running lint/typecheck/test for both apps on every PR. `DEVELOPER.md` is the new full setup/run/troubleshooting guide.

## Repo layout

```text
apps/api/app/    agents/ api/ core/ db/ events/ llm/ models/ retrieval/ schemas/ services/ tools/ workflows/   (full ARCHITECTURE.md §3 target module list; llm/ is a Phase 3 addition beyond it)
apps/web/src/    app/ (routes) components/ui/ components/layout/ features/ (feature modules) lib/ (api client, identity, cn helper)
packages/shared/ OpenAPI-generated TS types (api-types.ts) plus a hand-written re-export index (index.ts) -- see "API -> TypeScript types" above
data/demo/       synthetic sales_data.csv used by tests and the Analyst tool
```

## Dev commands

```powershell
# Backend (from apps/api, after activating .venv)
python -m pytest -q
python -m ruff check .
python -m mypy app
uvicorn app.main:app --reload --port 8000   # local dev server; see README for the auth header every request needs

# Regenerate packages/shared's TS types after any route/schema change (from repo root)
python apps/api/scripts/export_openapi.py   # apps/api/.venv activated
npm run generate:api-types

# Frontend (from repo root)
npm run lint
npm run typecheck
npm run build

# Full stack
docker compose up --build
```

Environment: Windows, PowerShell primary, Bash tool available for POSIX scripts. The backend `.venv` already exists under `apps/api/.venv`; system Python does not have `langgraph` installed, so backend commands must run through that venv.

## Implementation roadmap

All 7 phases are done: ~~Foundation & Infrastructure~~ → ~~Data Models & Persistence~~ → ~~Business Logic (Agents/Tools/Retrieval)~~ → ~~Workflow Orchestration~~ → ~~APIs~~ → ~~Frontend/UI~~ → ~~Tests & Quality Gates~~. See "Current state vs. target" above and `DEVELOPER.md` for how to run everything locally, or `DEPLOYMENT.md` for how to put a public instance online on free-tier hosting (Vercel + Render + Neon + Upstash + Groq/Hugging Face — see the AGENTS.md exception this documents).
