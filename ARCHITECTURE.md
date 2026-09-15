# AegisOS Architecture

## 1. Purpose and Day-1 scope

AegisOS is an autonomous enterprise AI workforce platform. A user submits a high-level business directive (e.g. *"Prepare next month's business review"*), and the platform plans the work, instantiates a fleet of specialized agents to execute it, verifies and clears the result, and preserves an auditable record — rather than simply answering conversationally.

Day 1 is a locally runnable, single-user development deployment. It supports mission creation, LLM-generated plan review/approval, LangGraph-driven multi-agent execution (research, data/SQL, analysis, QA, compliance, reporting), retrieval-augmented context from an enterprise knowledge base, tool calls through controlled adapters (including sandboxed code execution and text-to-SQL), artifact delivery, and audit inspection. It runs entirely on free, self-hostable, open-source components — local Ollama/Hugging Face open-weight models, PostgreSQL with pgvector, optional Qdrant, Redis, and Docker Compose. It does **not** require any paid SaaS dependency, a multi-tenant control plane, or fully autonomous irreversible actions.

## 2. Architectural principles

- Keep orchestration deterministic around model decisions: every state transition is explicit, LangGraph-driven, and recorded — this holds even as agents gain delegation and messaging capabilities (see §7).
- Treat all model output as untrusted input: plans, findings, generated SQL, and generated Python code are validated or sandboxed before they can affect real state. Generated code is never `eval`'d in-process; it only ever runs inside the governed sandbox tool adapter.
- Require human approval before execution by default, and require it again at the Compliance gate before any report leaves the system (see §7, §12).
- Separate the UI, API/orchestrator, persistence, and integrations so each can evolve independently.
- Persist durable mission state and audit events in PostgreSQL; do not rely on in-memory graph state for recovery. SQLite checkpointing (already implemented) is an acceptable Day-1 durability mechanism and is promotable to a Postgres-backed LangGraph checkpointer without changing the graph.
- Use provider-neutral interfaces for LLMs, tools, vector retrieval, and background execution.
- Keep the long-term knowledge layer (retrieval corpus) architecturally separate from short-term execution state (a mission run): the former is rebuildable; the run/checkpoint/audit trail is the durable record of what actually happened.

## 3. Modular monorepo

```text
aegisos/
+-- apps/
|   +-- web/                    # Next.js UI
|   +-- api/                    # FastAPI application and LangGraph orchestration
+-- packages/
|   +-- shared/                 # Shared TypeScript API contracts and utilities
+-- data/
|   +-- demo/                   # Non-sensitive local demo inputs only
+-- infra/
|   +-- docker/                 # Dockerfiles and service configuration
|   +-- compose/                # Compose overrides/profiles
+-- docs/                       # ADRs, runbooks, API examples
+-- scripts/                    # Explicit developer and CI commands
+-- requirements.md              # Product requirements (source of truth for scope)
+-- AGENTS.md
+-- ARCHITECTURE.md
+-- README.md
+-- docker-compose.yml
```

Python backend modules live under `apps/api/app/`: `api`, `core`, `db`, `models`, `schemas`, `services`, `agents`, `tools`, `workflows`, `events`, and `retrieval`. UI features live under `apps/web/src/features/`; shared route/layout code remains in `src/app/`. `packages/shared` splits into `contracts`, `ui`, and `prompts` only once those independently shared concerns exist.

## 4. System architecture

```text
Browser -> Next.js web -> FastAPI REST + SSE
                           |
                           +-- PostgreSQL + pgvector (missions, plans, runs, audit, knowledge)
                           +-- Redis (event bus / SSE fan-out, ephemeral coordination)
                           +-- LangGraph workflow + agent services -> Ollama / Hugging Face models
                           +-- Tool registry -> governed adapters (retrieval, SQL, sandboxed code, docs)
                           +-- Qdrant (optional, larger-scale retrieval profile)
                           +-- DuckDB/Pandas (bounded analysis jobs)
                           +-- Langfuse (self-hosted LLM tracing/observability)
```

FastAPI is the system boundary and owns authorization, validation, persistence, orchestration commands, and event streaming. LangGraph is an internal workflow implementation detail, never directly exposed to the browser. PostgreSQL is the source of truth for relational and vector (pgvector) data; Qdrant, when enabled, is a rebuildable retrieval index for larger corpora. Redis carries no durable state — it is a fan-out/coordination layer only.

## 5. Frontend architecture

Next.js App Router with TypeScript and Tailwind CSS provides a responsive operator console. shadcn/ui primitives are wrapped in `packages/shared` only when shared behavior or styling is needed.

Primary screens: mission list, mission detail (goal, plan, approvals, live run timeline), knowledge base management (document ingestion status), artifact/report viewer, audit explorer, and settings. Feature modules own components, query hooks, and view models. The UI calls the versioned FastAPI API via contracts in `packages/shared`; generated OpenAPI types replace hand-written contracts as the API expands. Server-sent events (backed by the Redis event bus) update active mission timelines; REST remains the source for initial and recovery reads. The frontend must never call Ollama, PostgreSQL, Redis, Qdrant, or tools directly.

## 6. Backend architecture

FastAPI routers translate HTTP into application services. Services enforce use cases such as creating a mission, approving a plan, or ingesting a knowledge document. Repositories isolate SQLAlchemy/PostgreSQL access. Pydantic request, response, graph-state, tool-input, and model-output schemas are distinct. Alembic manages schema migrations.

The API process can execute one bounded run synchronously/asynchronously for Day 1; the request returns a `run_id`, while workflow progress is persisted and delivered through SSE (fanned out via Redis). A process restart marks an interrupted run recoverable and permits an explicit resume from the last LangGraph checkpoint. Avoid a dedicated job queue/broker beyond Redis pub/sub until concurrent or long-running workloads demand one.

## 7. Agent and workflow architecture

Agents are role-specific services sharing common LLM, prompt, retrieval, tool-policy, and structured-output components. The roster below reflects the topology in `requirements.md`:

| Agent | Responsibility |
|---|---|
| **Orchestrator** (AI Manager) | Normalizes the mission, produces an LLM-generated plan of dependent tasks, dispatches tasks, handles retry/replan decisions, assembles the final result. |
| **Research** | Gathers context via hybrid retrieval (vector + keyword) over the enterprise knowledge base, plus allowlisted external HTTP retrieval when enabled. Returns only real, attributed `Evidence` — never a synthesized source. |
| **Data** | Text-to-SQL: inspects registered schemas and answers structured questions against PostgreSQL through a least-privilege, read-only role. Never emits or executes non-`SELECT` statements. |
| **Analyst** | Tabular/CSV analysis (Pandas/DuckDB) and bounded, sandboxed Python code execution for statistical modeling beyond the prebuilt analysis functions. |
| **QA** | Cross-checks every finding for evidentiary support, runs groundedness/hallucination checks (claim-to-evidence comparison, LLM self-critique), and requests correction or retry for unsupported claims. |
| **Compliance** | Reviews QA-passed findings and the draft report against policy/PII/regulatory rules; decides whether delivery can proceed or must escalate to human approval. |
| **Report** | Assembles the executive report (and, where requested, a slide deck) strictly from QA-cleared and Compliance-cleared findings, with facts and recommendations kept clearly separate. |

The Day-1 graph is:

```text
intake -> plan (orchestrator, LLM) -> await_approval
       -> dispatch -> {research | data | analyst}   (dependency-ordered, parallel-eligible)
       -> dispatch -> qa -> (retry | replan -> await_approval | compliance)
       -> compliance -> (escalate_approval | report)
       -> report -> finalize
```

Failed QA allows one configured retry or a replan proposal; a replan that materially changes scope returns to `await_approval`. A Compliance verdict that requires human sign-off routes to an `escalate_approval` state rather than delivering automatically. Every transition persists a checkpoint, run status, and audit event, as already implemented by `AegisRuntime`'s `_dispatch`/`_route`/checkpoint pattern — that mechanism extends to the new nodes rather than being replaced.

### Agent communication

LangGraph's explicit edges remain the single source of control flow — this is intentional and does not change with `requirements.md`'s "peer-to-peer delegation, message-bus" capability. A Redis-backed event stream publishes every state transition and audit event for SSE fan-out to the UI, and doubles as a notification channel between agents (e.g. QA flags a finding, Analyst is notified to re-run). This is publish/subscribe *notification*, not direct invocation: any delegation always re-enters the graph through the orchestrator/dispatch node so approval, retries, and audit stay centralized and replayable. Where an agent-orchestration library like CrewAI is used, it is scoped to a single node's internal sub-task loop (e.g. the Analyst agent coordinating a short internal tool-use sequence) and never owns cross-node control flow — LangGraph is the only authority over mission-level state transitions.

### Memory

- **Short-term (execution/working memory):** `AegisState`, unchanged in shape from the current `workflows/state.py` implementation — JSON-only, versioned, checkpointed. SQLite is the Day-1 checkpoint store; a Postgres-backed LangGraph checkpointer is a drop-in upgrade.
- **Long-term (knowledge memory):** embeddings of ingested `knowledge_documents`, stored in pgvector by default (co-located with relational data, no extra service), with an optional Qdrant profile for larger or standalone retrieval workloads. Indexed and queried through LlamaIndex. Agents never write to the knowledge store directly — ingestion is an explicit, audited pipeline (`POST /knowledge/documents`).

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
| `tool_executions` | run/step, tool/version, sanitized input/output, status, duration, risk level |
| `sql_queries` | Data agent: statement, target schema, row count, duration, run/task id |
| `code_executions` | Analyst agent sandbox: script hash, resource usage, exit status, redacted stdout/stderr |
| `compliance_reviews` | finding/report id, rule set version, verdict, reviewer, escalation reference |
| `artifacts` | mission/run, type, storage URI, checksum, metadata |
| `knowledge_documents` | workspace, source metadata, ingestion status, checksum |
| `knowledge_chunks` | document, chunk text, pgvector embedding, non-sensitive filter metadata |
| `audit_events` | append-only actor/action/resource/correlation/payload/timestamp |

Store flexible plan/state metadata in PostgreSQL `JSONB`, but promote query-critical fields to columns. Store small Day-1 artifacts on a mounted local volume with metadata/checksum in PostgreSQL; abstract this behind an artifact store for later S3-compatible storage. `knowledge_chunks.embedding` uses pgvector as the Day-1 default; if a Qdrant profile is enabled, Qdrant collections store the same embeddings plus document/chunk IDs and non-sensitive filter metadata, kept in sync by the ingestion pipeline.

DuckDB and Pandas run inside analysis tool adapters over explicitly staged inputs. They are not the system of record and may not freely read host directories or production databases.

## 9. API surface

Product routes are versioned under `/api/v1` and use Pydantic contracts. The unversioned `GET /health` infrastructure liveness endpoint is the explicit exception. Every workspace-scoped route is nested under `/workspaces/{workspace_id}/...` rather than taking the workspace as an implicit query parameter, so the RBAC dependency (§12) has one unambiguous path segment to enforce on — this is a deliberate refinement of the API shape, made once the runtime existed to build against.

Plan generation is **not** a separate step from starting a run: the LangGraph runtime plans (an LLM call) as the first thing a run does, immediately followed by the mandatory approval gate (§7) — so there is no `POST /missions/{id}/plan` distinct from `POST .../runs`, and a mission's plan is only readable once a run has produced one (`GET .../runs/{run_id}` shows it; `mission_plans` rows are a projection backfilled from the checkpoint, not the primary write path). One `/runs/{run_id}/approvals` endpoint resolves *whichever* human gate is currently open — the initial plan approval or a later Compliance escalation — since both map onto the same `AegisRuntime` approve/reject/resolve-escalation calls and a run is only ever awaiting one of them at a time.

| Method | Endpoint | Purpose | Minimum role |
|---|---|---|---|
| `POST` | `/workspaces` | Create a workspace (creator becomes admin) | *(any authenticated user)* |
| `GET` | `/workspaces` | List workspaces the caller belongs to | *(any authenticated user)* |
| `POST` | `/workspaces/{workspace_id}/missions` | Create a draft mission | operator |
| `GET` | `/workspaces/{workspace_id}/missions` | List missions | viewer |
| `GET` | `/workspaces/{workspace_id}/missions/{mission_id}` | Read mission and status | viewer |
| `POST` | `/workspaces/{workspace_id}/missions/{mission_id}/runs` | Plan and start a run (202, executes in the background) | operator |
| `GET` | `/workspaces/{workspace_id}/runs/{run_id}` | Read live run state from the checkpoint (§6) | viewer |
| `POST` | `/workspaces/{workspace_id}/runs/{run_id}/approvals` | Approve/reject whichever gate is open | reviewer |
| `POST` | `/workspaces/{workspace_id}/runs/{run_id}/resume` | Explicitly resume a recoverable run | operator |
| `POST` | `/workspaces/{workspace_id}/runs/{run_id}/cancel` | Request safe cancellation | operator |
| `GET` | `/workspaces/{workspace_id}/runs/{run_id}/events` | SSE workflow/audit event stream | viewer |
| `GET` | `/workspaces/{workspace_id}/missions/{mission_id}/artifacts` | List delivery artifacts (reports, slide decks) | viewer |
| `GET` | `/workspaces/{workspace_id}/audit-events` | Filterable audit search (`run_id`, `event_type`) | viewer |
| `POST` | `/workspaces/{workspace_id}/knowledge/documents` | Ingest a knowledge document | operator |
| `GET` | `/workspaces/{workspace_id}/knowledge/documents` | List knowledge documents and ingestion status | viewer |

Authentication is a documented local-development identity mode only (§12): callers send an `X-Aegis-Identity-Subject` header (optionally `X-Aegis-Display-Name`), auto-provisioned into a `User` row on first sight. This is explicitly not production authentication and must be replaced by a real identity provider before any non-dev deployment. OpenAPI is generated by FastAPI (`apps/api/scripts/export_openapi.py`) and is the source for the TypeScript types generated into `packages/shared` (`npm run generate:api-types`) — never hand-write request/response types in the frontend.

## 10. Tool architecture

Tools implement a narrow adapter protocol: `name`, `version`, input/output Pydantic schemas, risk level, required permissions, execution function, and redaction rules. The registry is allowlist-only. Agents may propose a tool call; policy validates agent role, workspace permission, plan-step scope, risk, and approval before executing it.

Tool classes and their risk posture:

- **Low risk:** knowledge retrieval (vector search over the ingested corpus), Pandas/DuckDB analysis over explicitly staged files.
- **Medium risk:** allowlisted external HTTP retrieval (timeouts, domain allowlist); text-to-SQL execution, restricted to a least-privilege read-only database role that rejects any non-`SELECT` statement before execution, with row and time limits.
- **High risk — always sandboxed, always audited, approval-gated by default:** Python code execution. Runs inside an isolated, non-networked, resource- and time-bounded environment with no host filesystem access beyond a disposable scratch directory, no ability to install arbitrary packages, and a capped output size. Generated code is treated as untrusted data end-to-end; it is never executed in the API process.

No unrestricted shell, arbitrary filesystem, database-write, or external side-effect tool is enabled in Day 1. Report/slide-deck generation only ever reads QA-cleared and Compliance-cleared findings — never raw agent or model output. Tool adapters use timeouts, size limits, structured outputs, idempotency keys where relevant, and audit emission before and after execution.

## 11. Events, observability, and audit

Domain events include `mission.created`, `plan.generated`, `plan.approved`, `run.started`, `agent.invoked`, `tool.requested`, `tool.completed`, `sql.executed`, `code.executed`, `knowledge.ingested`, `qa.completed`, `compliance.reviewed`, `approval.escalated`, `run.replanned`, `artifact.created`, and `run.completed/failed/cancelled`.

Every important event is written transactionally to append-only `audit_events`, with actor type/id, action, resource type/id, run and correlation IDs, timestamp, outcome, and redacted structured metadata. Audit records are never edited by application code; correction is a new event. The current in-process `AuditSink` is a Day-1 stand-in and must be backed by this persistent table before the durability guarantee in this section holds — that swap is tracked as outstanding work, not yet implemented. SSE publishes persisted events (via the Redis bus) after commit, so reconnecting clients can recover from the API.

Every LLM call (planning, QA critique, compliance review) is traced through self-hosted Langfuse with prompt template, model, token, and cost metadata, correlated to `run_id`/`task_id`. Langfuse never receives data outside the local/self-hosted deployment. Logs are structured JSON and correlate with audit/run IDs. Metrics start with request latency, run duration/status, node/tool errors, and model/tool latency; distributed tracing is a later addition.

## 12. Security and governance model

- Enforce workspace-scoped RBAC: `admin`, `operator`, `reviewer`, `viewer`.
- Authenticate every non-development request; authorize every resource access at the service layer.
- Keep secrets in environment variables or a future secret manager, never prompts, events, artifacts, or source control.
- Redact credentials and sensitive fields from model context, logs, audit payloads, and tool records.
- Define model/tool allowlists, input limits, output schemas, rate limits, request timeouts, and explicit egress controls.
- The sandboxed code-execution environment is network-disabled by default, runs as a non-root, least-privilege process/container per execution, and is torn down after each run — no persistent state carries between executions.
- The Data agent's database role is read-only and schema-scoped; any generated statement that is not a `SELECT` is rejected before execution, not merely logged.
- The Compliance gate is mandatory before any report or artifact is marked deliverable; a Compliance verdict requiring escalation blocks delivery until a human reviewer resolves it.
- Record prompt template/model/tool versions and retrieval references for reproducibility.
- Require human approval for plan execution, scope-changing replans, and Compliance escalations; preserve plan and approval versions.
- Use least-privilege service accounts and non-root containers. TLS is terminated by the deployment environment; local Compose is development-only.

## 13. Testing strategy

- Unit tests: pure domain services, policies, schemas, graph routing, redaction, and tool adapters.
- Integration tests: FastAPI plus disposable PostgreSQL (with pgvector) and optional Qdrant, migrations, repository behavior, SSE recovery, and policy enforcement.
- Workflow tests: deterministic fake LLM/tool fixtures for success, retry, replan, cancel, resume, QA-failure, and Compliance-escalation paths.
- Tool safety tests: sandbox resource/network isolation for code execution, SQL statement allowlisting for the Data agent, retrieval relevance fixtures for the Research agent.
- Contract tests: OpenAPI snapshots and generated frontend client compatibility.
- UI tests: component tests and Playwright flows for mission → approval → run → artifact/audit viewing.
- Security tests: authorization matrix, prompt-injection/tool-policy fixtures, secret-redaction assertions, sandbox escape fixtures, and dependency/container scanning in CI.

Never make CI depend on a live Ollama/Hugging Face model, a live network, or a live Langfuse instance. Maintain a small manually reviewed local smoke suite for the selected models.

## 14. Docker and local operations

`docker-compose.yml` runs `web`, `api`, `postgres` (pgvector-enabled), `redis`, and `ollama` on a shared internal network. Qdrant is supplied by an optional `retrieval` Compose profile; Langfuse (with its own storage) is supplied by an optional `observability` Compose profile. Named volumes persist PostgreSQL, Redis (if persistence is desired), Ollama model data, Qdrant when enabled, and local artifacts. Health-gated dependency startup is added once persistence is wired into the API. Ollama/Hugging Face model pulling is an explicit documented bootstrap step rather than an implicit startup download.

Expose only the web/API ports needed for local use. Service-to-service hostnames are Compose service names; no frontend database credentials exist. Provide `.env.example` with non-secret defaults and required variable descriptions; never commit `.env`.

## 15. Scalability path

Keep the Day-1 interfaces stable while scaling incrementally:

1. Move run execution to a durable worker queue and use a shared LangGraph checkpoint store (Postgres-backed).
2. Replace local artifacts with S3-compatible object storage and add an outbox/event bus (Redis pub/sub is the Day-1 seed for this).
3. Horizontally scale stateless API/web services; partition workers by tool capability and risk class (isolate code-execution workers from everything else).
4. Introduce tenant quotas, per-tenant Qdrant collections/filters, model routing across a larger open-weight model catalog, and stronger identity integration.
5. Add CI (GitHub Actions) quality gates and an optional free-tier hosted deployment (Render/Railway) for a shared demo instance, without making either a Day-1 requirement.
6. Add richer observability backends beyond Langfuse, evaluation datasets, governance dashboards, retention policies, and regional deployment only when product needs justify them.

This path deliberately avoids premature microservices: the Day-1 backend remains a modular FastAPI application with clear seams.
