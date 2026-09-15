# AegisOS

AegisOS is a local-first Autonomous Enterprise AI Workforce platform. The backend provides a full `/api/v1` HTTP API over a LangGraph-based multi-agent runtime — Orchestrator (LLM planning), Research, Data (text-to-SQL), Analyst (tabular analysis + sandboxed code execution), QA, Compliance, and Report agents — with durable checkpointing, a human-in-the-loop approval/escalation gate, workspace-scoped RBAC, Postgres persistence, Redis-backed SSE, and OpenAPI-generated frontend types.

> The frontend (`apps/web`) is still a placeholder page and doesn't call the API yet — that's the only major piece left. Nothing in this repo has been exercised against a *live* Postgres/Redis/Ollama/Docker/Langfuse instance either: every backend test runs against a fake or an in-memory SQLite substitute (AGENTS.md). See [CLAUDE.md](CLAUDE.md) for the precise built-vs-target breakdown.

## Stack

| Area | Choice |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui configuration |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy + Alembic |
| Agent orchestration | LangGraph (state machine of record), LangChain-core, optional CrewAI (`crew` extra, scoped to a single node per [AGENTS.md](AGENTS.md)) |
| Retrieval | pgvector (default vector store), LlamaIndex, optional Qdrant |
| Local services | Docker Compose, PostgreSQL with pgvector, Redis, Ollama / Hugging Face open-weight models, optional self-hosted Langfuse |
| Shared contracts | npm workspace package (`@aegisos/shared`) |

## Repository layout

```text
apps/web          Next.js dashboard and API client
apps/api          FastAPI service, LangGraph agent runtime, and tests
packages/shared   Shared TypeScript API contracts
infra/docker      Container images and Postgres bootstrap scripts
data/demo         Reserved non-sensitive demo data
docs              Design decisions and runbooks
```

Project documentation, in reading order: [requirements.md](requirements.md) (product scope) → [ARCHITECTURE.md](ARCHITECTURE.md) (target system design) → [AGENTS.md](AGENTS.md) (binding development rules) → [CLAUDE.md](CLAUDE.md) (session orientation and built-vs-target status).

## Start with Docker (recommended)

Prerequisites: Docker Desktop with Compose enabled.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

This starts `web`, `api`, `postgres` (with the `pgvector` extension bootstrapped via `infra/docker/postgres/init-extensions.sql`), `redis`, and `ollama`. Open <http://localhost:3000>. The dashboard makes a browser request to `/backend/health`; Next.js proxies it to the FastAPI service. Verify the API directly with:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Start the optional retrieval service (Qdrant) only when it is needed:

```powershell
docker compose --profile retrieval up --build
```

Start the optional self-hosted observability stack (Langfuse, with its own Postgres) only when it is needed:

```powershell
docker compose --profile observability up --build
```

Langfuse is then reachable at `http://localhost:3001` (`LANGFUSE_PORT`); create a project there and copy its API keys into `AEGIS_LANGFUSE_PUBLIC_KEY`/`AEGIS_LANGFUSE_SECRET_KEY` in `.env` once the API actually sends traces (not yet wired — see [CLAUDE.md](CLAUDE.md)).

Stop services while retaining local volumes with `docker compose down`. Add `--volumes` only when you intentionally want to remove local PostgreSQL, Ollama, Qdrant, and Langfuse data. Redis holds no persistent volume by design (ephemeral event bus only, see [AGENTS.md](AGENTS.md)) — there is nothing to retain or lose there.

## Run without Docker

Prerequisites: Node.js 20.9+ with npm 10+, and Python 3.12.

```powershell
Copy-Item .env.example .env
npm install
Set-Location apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Add the optional `crew` extra (`pip install -e ".[dev,crew]"`) only if you're working on the CrewAI-backed sub-task loop scoped to the Analyst agent (see [AGENTS.md](AGENTS.md)) — it is not required for anything else.

In a second PowerShell window from the repository root:

```powershell
npm run dev
```

Open <http://localhost:3000>. The development rewrite uses `API_INTERNAL_URL` from `.env`, which defaults to `http://localhost:8000`.

Missions, runs, and knowledge ingestion genuinely need a reachable PostgreSQL (`AEGIS_DATABASE_URL`, migrated with `alembic upgrade head` from `apps/api`) — `GET /health` and the test suite are the only things that work with none of the local services running. Redis/Ollama/Docker are each used by a specific capability (SSE fan-out, LLM/embedding calls, sandboxed code execution) and degrade or fail only that capability, not the whole API, when unreachable.

### Environment variables

`.env.example` documents every variable; beyond the ones already covered above:

| Variable | Purpose |
|---|---|
| `REDIS_PORT`, `AEGIS_REDIS_URL` | Local Redis port and the DSN the API uses for the event bus/SSE fan-out |
| `AEGIS_DATABASE_URL` | SQLAlchemy DSN (psycopg v3 driver) for the pgvector-enabled PostgreSQL instance |
| `AEGIS_MODEL_PROVIDER`, `AEGIS_MODEL_NAME`, `AEGIS_EMBEDDING_MODEL_NAME` | Selects the local/open-weight chat and embedding models (`ollama` or `huggingface`) |
| `AEGIS_DATA_ROOT` | Where the Analyst agent's tabular tool reads staged CSVs from; defaults assume `uvicorn` runs from `apps/api` (docker-compose overrides it for the container) |
| `AEGIS_ARTIFACT_ROOT` | Where completed runs' reports (and embedded slide decks) are written as local-file artifacts |
| `AEGIS_SANDBOX_TIMEOUT_SECONDS`, `AEGIS_SANDBOX_MEMORY_LIMIT_MB`, `AEGIS_SANDBOX_CPU_LIMIT` | Resource limits for the Analyst agent's sandboxed code-execution tool |
| `LANGFUSE_PORT`, `LANGFUSE_DB_PASSWORD`, `LANGFUSE_NEXTAUTH_SECRET`, `LANGFUSE_SALT`, `LANGFUSE_ENCRYPTION_KEY` | Configuration for the self-hosted Langfuse container (`observability` Compose profile) |
| `AEGIS_LANGFUSE_HOST`, `AEGIS_LANGFUSE_PUBLIC_KEY`, `AEGIS_LANGFUSE_SECRET_KEY` | Where the API's Langfuse client sends traces, and its project API keys (tracing auto-enables once both keys are set) |

### Applying database migrations

```powershell
Set-Location apps/api
alembic upgrade head
```

Run this once against a fresh PostgreSQL instance (or after pulling a change that touches `apps/api/app/models/`) before using any route beyond `GET /health`.

## Validation commands

```powershell
# Frontend, from the repository root
npm run lint
npm run typecheck
npm run build

# Backend, after activating apps/api/.venv
Set-Location apps/api
pytest
ruff check .
mypy app
```

### Regenerating `packages/shared`'s API types

After changing anything under `apps/api/app/api/` or a Pydantic request/response schema it uses, regenerate `packages/shared`'s TypeScript types rather than hand-editing them:

```powershell
Set-Location apps/api
python scripts/export_openapi.py
Set-Location ../..
npm run generate:api-types
```

This writes `packages/shared/openapi.json` and `packages/shared/src/api-types.ts`; commit both.

## Current API

`GET /health` returns the service name, version, environment, and an `ok` status, unversioned. Everything else is versioned under `/api/v1` — see [ARCHITECTURE.md §9](ARCHITECTURE.md#9-api-surface) for the full route table. Every `/api/v1` route requires an `X-Aegis-Identity-Subject` header (a documented **local development identity mode only** — see [AGENTS.md](AGENTS.md) and [ARCHITECTURE.md §12](ARCHITECTURE.md#12-security-and-governance-model) — never mistake it for real authentication); the identity is auto-provisioned into a `User` row on first request, and workspace access is enforced by role (viewer/reviewer/operator/admin) via `apps/api/app/api/deps.py`.

A minimal end-to-end flow, once `docker compose up` (or the no-Docker setup plus `alembic upgrade head`) is running:

```powershell
$headers = @{ "X-Aegis-Identity-Subject" = "you@example.com" }

$workspace = Invoke-RestMethod -Method Post http://localhost:8000/api/v1/workspaces `
  -Headers $headers -ContentType "application/json" -Body '{"name":"Acme"}'

$mission = Invoke-RestMethod -Method Post "http://localhost:8000/api/v1/workspaces/$($workspace.id)/missions" `
  -Headers $headers -ContentType "application/json" `
  -Body '{"raw_request":"Analyze sales performance.","objective":"Analyze sales performance and produce an executive summary.","context":{"dataset_path":"sales_data.csv"}}'

$run = Invoke-RestMethod -Method Post "http://localhost:8000/api/v1/workspaces/$($workspace.id)/missions/$($mission.id)/runs" -Headers $headers
# $run.status is "running" briefly, then the run pauses for approval once planning completes:
Invoke-RestMethod "http://localhost:8000/api/v1/workspaces/$($workspace.id)/runs/$($run.run_id)" -Headers $headers

Invoke-RestMethod -Method Post "http://localhost:8000/api/v1/workspaces/$($workspace.id)/runs/$($run.run_id)/approvals" `
  -Headers $headers -ContentType "application/json" -Body '{"decision":"approve"}'
```

`GET /api/v1/workspaces/{workspace_id}/runs/{run_id}/events` streams the same run's audit trail as Server-Sent Events, tailing the Redis Stream `RedisEventBusSink` publishes to.

Architecture details are in [ARCHITECTURE.md](ARCHITECTURE.md); implementation rules are in [AGENTS.md](AGENTS.md); a precise built-vs-target status and the phased implementation roadmap are in [CLAUDE.md](CLAUDE.md).
