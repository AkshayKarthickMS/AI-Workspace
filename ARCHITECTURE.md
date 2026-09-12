# AegisOS Architecture

## 1. Purpose and Day-1 scope

AegisOS is an autonomous enterprise AI workforce platform. A user submits a business mission, the platform plans and executes bounded work through specialized agents, verifies the outcome, and preserves an auditable record.

Day 1 is a locally runnable, single-user development deployment. It supports mission creation, plan review/approval, graph-driven execution, tool calls through controlled adapters, artifact delivery, and audit inspection. It uses local Ollama models and Docker Compose. It does **not** require cloud services, distributed workers, a multi-tenant control plane, or fully autonomous irreversible actions.

## 2. Architectural principles

- Keep orchestration deterministic around model decisions: every state transition is explicit and recorded.
- Treat model output as untrusted input; validate it with Pydantic schemas before use.
- Require human approval before execution by default and before any future high-impact tool action.
- Separate the UI, API/orchestrator, persistence, and integrations so each can evolve independently.
- Persist durable mission state and audit events in PostgreSQL; do not rely on in-memory graph state for recovery.
- Use provider-neutral interfaces for LLMs, tools, vector retrieval, and background execution.

## 3. Modular monorepo

```text
aegisos/
+-- apps/
|   +-- web/                    # Next.js UI
|   +-- api/                    # FastAPI application and LangGraph orchestration
+-- packages/
|   +-- shared/                 # Day-1 shared TypeScript API contracts and utilities
+-- data/
|   +-- demo/                   # Non-sensitive local demo inputs only
+-- infra/
|   +-- docker/                 # Dockerfiles and service configuration
|   +-- compose/                # Compose overrides/profiles
+-- docs/                       # ADRs, runbooks, API examples
+-- scripts/                    # Explicit developer and CI commands
+-- AGENTS.md
+-- ARCHITECTURE.md
+-- README.md
+-- docker-compose.yml
```

Python backend modules live under `apps/api/app/`: `api`, `core`, `db`, `models`, `schemas`, `services`, `agents`, `tools`, `workflows`, and `events`. UI features live under `apps/web/src/features/`; shared route/layout code remains in `src/app/`. The initial `packages/shared` module may be split into `contracts`, `ui`, and `prompts` only once those independently shared concerns exist.

## 4. System architecture

```text
Browser -> Next.js web -> FastAPI REST + SSE
                           |
                           +-- PostgreSQL (missions, plans, runs, audit, artifacts)
                           +-- LangGraph workflow + agent services -> Ollama
                           +-- Tool registry -> local/sandboxed tool adapters
                           +-- Qdrant (optional knowledge retrieval)
                           +-- DuckDB/Pandas (bounded analysis jobs)
```

FastAPI is the system boundary and owns authorization, validation, persistence, orchestration commands, and event streaming. LangGraph is an internal workflow implementation detail, never directly exposed to the browser. PostgreSQL is the source of truth; Qdrant is a rebuildable retrieval index.

## 5. Frontend architecture

Next.js App Router with TypeScript and Tailwind CSS provides a responsive operator console. shadcn/ui primitives are wrapped in `packages/shared` only when shared behavior or styling is needed.

Primary screens: mission list, mission detail (goal, plan, approvals, live run timeline), artifact viewer, audit explorer, and settings. Feature modules own components, query hooks, and view models. The UI calls the versioned FastAPI API via contracts in `packages/shared`; generated OpenAPI types can replace the initial hand-written health contract when the API expands. Server-sent events update active mission timelines; REST remains the source for initial and recovery reads. The frontend must never call Ollama, PostgreSQL, Qdrant, or tools directly.

## 6. Backend architecture

FastAPI routers translate HTTP into application services. Services enforce use cases such as creating a mission or approving a plan. Repositories isolate SQLAlchemy/PostgreSQL access. Pydantic request, response, graph-state, tool-input, and model-output schemas are distinct. Alembic manages schema migrations.

The API process can execute one bounded run synchronously/asynchronously for Day 1; the request returns a `run_id`, while workflow progress is persisted and delivered through SSE. A process restart marks an interrupted run recoverable and permits an explicit resume. Avoid a queue/broker until concurrent or long-running workloads demand one.

## 7. Agent and workflow architecture

Agents are role-specific services sharing common LLM, prompt, retrieval, tool-policy, and structured-output components:

- **Planner:** transforms a mission into ordered, measurable plan steps.
- **Research/analysis worker:** gathers permitted context and performs bounded analysis.
- **Execution worker:** completes an assigned step using approved tools.
- **Verifier:** evaluates outputs against step acceptance criteria and evidence.
- **Supervisor:** selects the next step, handles retry/replan decisions, and assembles the final result.

The Day-1 graph follows: `intake -> plan -> await_approval -> dispatch_step -> execute -> verify -> (next_step | replan | finalize)`. Failed verification allows one configured retry or a replan proposal; a replan that materially changes scope returns to approval. Each transition persists a checkpoint, run status, and audit event.

### LangGraph state

Use a Pydantic-compatible, JSON-serializable state model; persist a checkpoint reference rather than arbitrary Python objects.

| Field | Meaning |
|---|---|
| `mission_id`, `run_id`, `tenant_id` | Correlation and ownership keys |
| `mission` | Normalized objective, constraints, success criteria |
| `plan` | Versioned steps, dependencies, acceptance criteria |
| `current_step_id` | Active plan step |
| `step_results` | Structured outputs and artifact references per step |
| `messages_summary` | Bounded conversation/working-context summary |
| `retrieval_refs` | Knowledge document/chunk references used |
| `tool_calls` | Proposed/executed call records, never secrets |
| `verification` | Latest verdict, evidence, and remediation request |
| `approval` | Required/received approval state |
| `retry_count`, `replan_count` | Bounded control-flow counters |
| `status`, `error` | Run status and safe error metadata |

## 8. Data architecture and schema

PostgreSQL tables (all include UUID primary keys, `created_at`, `updated_at` where applicable):

| Table | Key contents |
|---|---|
| `users` | identity provider subject, display name, role |
| `workspaces` | ownership boundary and settings |
| `workspace_members` | user/workspace role membership |
| `missions` | workspace, title, raw request, normalized request, status, creator |
| `mission_plans` | mission, version, JSON plan, status, approver |
| `plan_steps` | plan, order, agent role, input, acceptance criteria, status |
| `runs` | mission/plan, graph version, status, timestamps, error summary |
| `run_checkpoints` | run, sequence, serialized state reference/payload, node name |
| `tool_executions` | run/step, tool/version, sanitized input/output, status, duration |
| `artifacts` | mission/run, type, storage URI, checksum, metadata |
| `knowledge_documents` | workspace, source metadata, ingestion status, checksum |
| `audit_events` | append-only actor/action/resource/correlation/payload/timestamp |

Store flexible plan/state metadata in PostgreSQL `JSONB`, but promote query-critical fields to columns. Store small Day-1 artifacts on a mounted local volume with metadata/checksum in PostgreSQL; abstract this behind an artifact store for later S3-compatible storage. Qdrant collections store embeddings and only document/chunk IDs plus non-sensitive filter metadata.

DuckDB and Pandas run inside analysis tool adapters over explicitly staged inputs. They are not the system of record and may not freely read host directories or production databases.

## 9. API surface

Product routes are versioned under `/api/v1`, use Pydantic contracts, return typed errors, and carry a correlation ID. The unversioned `GET /health` infrastructure liveness endpoint is the explicit exception.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/missions` | Create a draft mission |
| `GET` | `/missions` | List visible missions |
| `GET` | `/missions/{mission_id}` | Read mission, latest plan, and status |
| `POST` | `/missions/{mission_id}/plan` | Generate or regenerate a draft plan |
| `POST` | `/missions/{mission_id}/approvals` | Approve or reject a plan/replan |
| `POST` | `/missions/{mission_id}/runs` | Start an approved plan |
| `GET` | `/runs/{run_id}` | Read run state and summary |
| `POST` | `/runs/{run_id}/resume` | Explicitly resume a recoverable run |
| `POST` | `/runs/{run_id}/cancel` | Request safe cancellation |
| `GET` | `/runs/{run_id}/events` | SSE workflow/audit event stream |
| `GET` | `/missions/{mission_id}/artifacts` | List delivery artifacts |
| `GET` | `/audit-events` | Filterable audit search |
| `POST` | `/knowledge/documents` | Upload/register a knowledge document (future-ready) |

Authentication endpoints are delegated to the selected identity provider; Day 1 may use a documented local development identity mode only. OpenAPI is generated by FastAPI and is the source for TypeScript client generation.

## 10. Tool architecture

Tools implement a narrow adapter protocol: `name`, `version`, input/output Pydantic schemas, risk level, required permissions, execution function, and redaction rules. The registry is allowlist-only. Agents may propose a tool call; policy validates agent role, workspace permission, plan-step scope, risk, and approval before executing it.

Initial tool classes: knowledge retrieval, HTTP retrieval restricted by allowlist/timeouts (if enabled), document/artifact creation, and Pandas/DuckDB analysis. No unrestricted shell, arbitrary filesystem, database-write, or external side-effect tool is enabled in Day 1. Tool adapters use timeouts, size limits, structured outputs, idempotency keys where relevant, and audit emission before and after execution.

## 11. Events, observability, and audit

Domain events include `mission.created`, `plan.generated`, `plan.approved`, `run.started`, `agent.invoked`, `tool.requested`, `tool.completed`, `verification.completed`, `run.replanned`, `artifact.created`, and `run.completed/failed/cancelled`.

Every important event is written transactionally to append-only `audit_events`, with actor type/id, action, resource type/id, run and correlation IDs, timestamp, outcome, and redacted structured metadata. Audit records are never edited by application code; correction is a new event. SSE publishes persisted events after commit, so reconnecting clients can recover from the API. Logs are structured JSON and correlate with audit/run IDs. Metrics start with request latency, run duration/status, node/tool errors, and model/tool latency; distributed tracing is a later addition.

## 12. Security and governance model

- Enforce workspace-scoped RBAC: `admin`, `operator`, `reviewer`, `viewer`.
- Authenticate every non-development request; authorize every resource access at the service layer.
- Keep secrets in environment variables or a future secret manager, never prompts, events, artifacts, or source control.
- Redact credentials and sensitive fields from model context, logs, audit payloads, and tool records.
- Define model/tool allowlists, input limits, output schemas, rate limits, request timeouts, and explicit egress controls.
- Record prompt template/model/tool versions and retrieval references for reproducibility.
- Require human approval for execution and scope-changing replans; preserve plan and approval versions.
- Use least-privilege service accounts and non-root containers. TLS is terminated by the deployment environment; local Compose is development-only.

## 13. Testing strategy

- Unit tests: pure domain services, policies, schemas, graph routing, redaction, and tool adapters.
- Integration tests: FastAPI plus disposable PostgreSQL/Qdrant, migrations, repository behavior, SSE recovery, and policy enforcement.
- Workflow tests: deterministic fake LLM/tool fixtures for success, retry, replan, cancel, and resume paths.
- Contract tests: OpenAPI snapshots and generated frontend client compatibility.
- UI tests: component tests and Playwright flows for mission → approval → run → artifact/audit viewing.
- Security tests: authorization matrix, prompt-injection/tool-policy fixtures, secret-redaction assertions, and dependency/container scanning in CI.

Never make CI depend on a live Ollama model. Maintain a small manually reviewed local smoke suite for the selected model.

## 14. Docker and local operations

`docker-compose.yml` runs `web`, `api`, `postgres`, and `ollama` on a shared internal network. Qdrant is supplied by an optional `retrieval` Compose profile. Named volumes persist PostgreSQL, Ollama model data, Qdrant when enabled, and local artifacts. The initial API does not require a data service; health-gated dependency startup is added only when persistence or retrieval is wired into the API. Ollama model pulling is an explicit documented bootstrap step rather than an implicit startup download.

Expose only the web/API ports needed for local use. Service-to-service hostnames are Compose service names; no frontend database credentials exist. Provide `.env.example` with non-secret defaults and required variable descriptions; never commit `.env`.

## 15. Scalability path

Keep the Day-1 interfaces stable while scaling incrementally:

1. Move run execution to a durable worker queue and use a shared LangGraph checkpoint store.
2. Replace local artifacts with S3-compatible object storage and add an outbox/event bus.
3. Horizontally scale stateless API/web services; partition workers by tool capability and risk class.
4. Introduce tenant quotas, per-tenant Qdrant collections/filters, model routing, and stronger identity integration.
5. Add observability backends, evaluation datasets, governance dashboards, retention policies, and regional deployment only when product needs justify them.

This path deliberately avoids premature microservices: the Day-1 backend remains a modular FastAPI application with clear seams.
