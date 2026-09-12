# AegisOS

AegisOS is a local-first foundation for an Autonomous Enterprise AI Workforce platform. This initial release provides the monorepo scaffold, a Next.js dashboard, a FastAPI health service, shared API types, Docker configuration, and operational guardrails.

> Agent workflows, mission execution, persistence, retrieval, and tool execution are intentionally not implemented yet. The dashboard labels those capabilities as planned rather than available.

## Stack

| Area | Choice |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui configuration |
| Backend | Python 3.12, FastAPI, Pydantic |
| Local services | Docker Compose, PostgreSQL, Ollama, optional Qdrant |
| Shared contracts | npm workspace package (`@aegisos/shared`) |

## Repository layout

```text
apps/web          Next.js dashboard and API client
apps/api          FastAPI service and health test
packages/shared   Shared TypeScript API contracts
infra/docker      Container images
data/demo         Reserved non-sensitive demo data
docs              Design decisions and runbooks
```

## Start with Docker (recommended)

Prerequisites: Docker Desktop with Compose enabled.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open <http://localhost:3000>. The dashboard makes a browser request to `/backend/health`; Next.js proxies it to the FastAPI service. Verify the API directly with:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Start the optional retrieval service only when it is needed:

```powershell
docker compose --profile retrieval up --build
```

Stop services while retaining local volumes with `docker compose down`. Add `--volumes` only when you intentionally want to remove local PostgreSQL, Ollama, and Qdrant data.

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

In a second PowerShell window from the repository root:

```powershell
npm run dev
```

Open <http://localhost:3000>. The development rewrite uses `API_INTERNAL_URL` from `.env`, which defaults to `http://localhost:8000`.

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

## Current API

`GET /health` returns the service name, version, environment, and an `ok` status. It is the only implemented product endpoint.

Architecture details are in [ARCHITECTURE.md](ARCHITECTURE.md); implementation rules are in [AGENTS.md](AGENTS.md).
