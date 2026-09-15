# Developer Guide

How to run AegisOS locally, what environment variables/keys go where, and how to run the checks CI runs. For architecture/scope, read `ARCHITECTURE.md`/`AGENTS.md`/`CLAUDE.md` first — this file is just the practical "get it running" reference.

## 1. Prerequisites

- Python 3.12 (backend)
- Node.js 20+ (frontend/monorepo tooling)
- Docker Desktop (only needed for `docker compose up`, or for the Analyst agent's sandboxed code execution — everything else runs without it)
- Nothing else is required to run the automated test suite. Postgres/Redis/Ollama are only needed for the *full* live stack; tests substitute SQLite/fakes for all of them (see `AGENTS.md`).

## 2. First-time setup

```powershell
# 1. Environment file — copy and edit (see section 4 for what each key does)
copy .env.example .env

# 2. Backend virtualenv + dependencies
cd apps\api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. Frontend dependencies (from repo root, installs the whole npm workspace)
cd ..\..
npm install
```

## 3. Running it

### Option A — full stack via Docker (closest to production shape)

```powershell
docker compose up --build
```

Starts Postgres, Redis, Ollama, the API, and the web app together. First run will also need you to pull a model into Ollama (see section 4).

- Web: http://localhost:3000
- API: http://localhost:8000 (docs at `/docs`)

### Option B — run API and web separately (faster iteration)

```powershell
# Terminal 1 — backend (from apps/api, venv activated)
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (from repo root)
npm run dev --workspace=@aegisos/web
```

The Next.js dev server proxies `/backend/*` to `API_INTERNAL_URL` (see `apps/web/next.config.ts`), so the frontend works against the API without CORS trouble.

Without Postgres/Redis/Ollama actually running, the API will start but any route that touches the database, event bus, or LLM will fail — Option B is meant to be paired with `docker compose up postgres redis ollama` (no `--build`, just the dependency containers) if you want a real backend, or you can point `AEGIS_DATABASE_URL` etc. at services you're already running.

## 4. Environment variables — what to paste where

All of these live in `.env` at the repo root (copied from `.env.example`). Docker Compose reads it directly; running the API outside Docker requires the same variables to be present in your shell/`.env` when `apps/api` starts.

| Variable | What it's for | What to put there |
|---|---|---|
| `AEGIS_DATABASE_URL` | Postgres connection string | Defaults work for the Compose Postgres container. Change only if pointing at an external database. |
| `AEGIS_REDIS_URL` | Event bus / SSE fan-out | Default works with the Compose Redis container. |
| `AEGIS_MODEL_PROVIDER` | Which LLM backend to use | `ollama` (default, local) or `huggingface` (any OpenAI-chat-compatible local server — TGI/vLLM/llama.cpp). **No cloud LLM API keys are used anywhere** — AGENTS.md requires local/open-weight models only. |
| `AEGIS_MODEL_NAME` | Chat model name | e.g. `qwen2.5:7b-instruct`. Must be pulled into Ollama first: `docker exec -it aegisos-ollama-1 ollama pull qwen2.5:7b-instruct` (or `ollama pull ...` directly if running Ollama natively). |
| `AEGIS_EMBEDDING_MODEL_NAME` | Embedding model for retrieval/QA | e.g. `nomic-embed-text`, pulled the same way. |
| `AEGIS_OLLAMA_BASE_URL` / `AEGIS_HUGGINGFACE_ENDPOINT_URL` | Where to reach the model server | Defaults assume the Compose service names / localhost. |
| `AEGIS_ARTIFACT_ROOT` / `AEGIS_DATA_ROOT` | Local filesystem paths for generated reports and the demo dataset | Defaults are fine for local dev. |
| `AEGIS_SANDBOX_*` | Resource limits for the Analyst agent's Docker-based code execution | Defaults are sane; only needed if you run code-execution paths, and only works if Docker is available to the API process. |
| `AEGIS_LANGFUSE_*` | Optional tracing | Leave blank to disable (default). To enable: run the `observability` Compose profile (`docker compose --profile observability up`), create a project in the local Langfuse UI at http://localhost:3001, and paste its public/secret keys here. Nothing is sent anywhere external — this is a self-hosted instance. |
| `AEGIS_CORS_ORIGINS` | Allowed frontend origin(s) | Default `http://localhost:3000` is correct for local dev. |

**There are no third-party SaaS API keys to configure.** No OpenAI/Anthropic/etc. keys are read anywhere in this codebase — that's a deliberate constraint, not an oversight (see `AGENTS.md`).

### Frontend "login"

There's no real auth yet — local development identity mode only (`ARCHITECTURE.md` §12). The first time you open the web app it'll ask you to set an "identity subject" (just an email-shaped string) and optional display name; this is stored in `localStorage` and sent as the `X-Aegis-Identity-Subject` header on every API call. Anyone can type any identity — it is not a security boundary, just how the API attributes actions in this phase.

## 5. Running the checks (what CI runs — `.github/workflows/ci.yml`)

```powershell
# Backend (from apps/api, venv activated)
python -m pytest -q
python -m ruff check .
python -m mypy app

# Frontend (from repo root)
npm run lint
npm run typecheck
npm run build
```

All of the above run against fakes/SQLite/mocks — no live Postgres/Redis/Ollama/Docker needed. If you change any API route or Pydantic schema, also regenerate the frontend's generated types (a committed contract test, `apps/api/tests/test_openapi_contract.py`, fails CI if you forget):

```powershell
# From apps/api, venv activated
python scripts/export_openapi.py
# From repo root
npm run generate:api-types
```

## 6. Test suite layout (what's covered where)

- `apps/api/tests/test_persistence.py` — repository layer (all 16 tables), migrations.
- `apps/api/tests/test_data_agent.py`, `test_qa_agent.py`, `test_compliance_agent.py` — the three newer agents.
- `apps/api/tests/test_sql_safety.py` — SQL statement-allowlist rejection.
- `apps/api/tests/test_code_execution.py` — sandbox network/filesystem isolation, resource/time limits, secret redaction in captured output.
- `apps/api/tests/test_redaction.py` — the redaction helper in isolation.
- `apps/api/tests/test_workflow_orchestration.py` — retry, replan, QA-failure, and Compliance-escalation graph paths.
- `apps/api/tests/test_api_runs.py` — full HTTP flow (mission → run → approval → completion → artifacts → audit), cancellation, and the authorization matrix (missing identity, non-member 404, viewer-role-forbidden).
- `apps/api/tests/test_openapi_contract.py` — fails if the API's schema drifts from the committed `packages/shared/openapi.json`.

**Known gap:** none of the above run against a *real* Postgres/pgvector/Redis/Ollama/Docker instance — everything substitutes SQLite or a fake per `AGENTS.md`. If you want to sanity-check against real infrastructure before a release, the simplest approach is `docker compose up` (section 3, Option A) and manually running through the golden path (create workspace → mission → run → approve → watch the live timeline → view an artifact) in the browser; there is no automated integration job for this yet.

## 7. Troubleshooting

- **API starts but every DB-touching route 500s**: Postgres isn't reachable — check `AEGIS_DATABASE_URL` and that the container/service is actually running.
- **Runs never leave `awaiting_approval`... after you approve**: check the API logs for LLM/Ollama connection errors — the Orchestrator, QA, and Report agents all need a reachable model server.
- **A run never even reaches `awaiting_approval`, and the API log shows `sqlite3.OperationalError: database is locked`**: only possible if you're running against SQLite instead of Postgres (not the documented setup, but sometimes used for a quick local check). On Windows, real-time antivirus scanning a frequently-written SQLite file is a well-known cause of this — add a Defender exclusion for the database's folder, or just use real Postgres (`docker compose up postgres`).
- **Sandboxed code execution fails immediately**: Docker isn't reachable from the API process. This is expected if you're running the API outside Docker without a local Docker daemon.
- **Frontend shows "API unavailable"**: the `/backend` rewrite proxy needs `API_INTERNAL_URL` (or the container's default) to reach a running API — confirm `http://localhost:8000/health` responds directly first.
