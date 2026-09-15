# AegisOS Development Rules

## Scope and approach

- Preserve the modular monorepo described in `ARCHITECTURE.md`; do not introduce application code outside its owning module without a clear reason.
- `requirements.md` is the source of truth for product scope (agent roster, capabilities, technology stack). `ARCHITECTURE.md` translates it into a buildable Day-1 system; when the two appear to disagree, treat `requirements.md` as intent and raise the conflict rather than silently picking one.
- Prefer the smallest production-quality change that satisfies the requested behavior. Do not add distributed infrastructure, external paid SaaS dependencies, or autonomous side-effect tools without explicit approval.
- Before editing, inspect nearby code, existing tests, and current Git changes. Preserve unrelated work.
- Update architecture/docs when a change alters a public contract, persistent schema, security boundary, agent roster, workflow, or local setup.

## Technology boundaries

- Web: Next.js, TypeScript, Tailwind, and shadcn/ui. Keep business decisions in the backend.
- API: Python, FastAPI, Pydantic, LangGraph, PostgreSQL. Use explicit dependencies, typed schemas, and Alembic migrations.
- AI: access local, open-weight models (Ollama and/or Hugging Face model families such as Qwen/Llama/Gemma) only through a provider interface — never a paid hosted model API. Require structured, validated outputs; never treat generated text, generated SQL, or generated code as directly executable instructions. LangGraph is the sole authority over mission-level control flow; LangChain and LlamaIndex are utility libraries used inside nodes/tools, not alternate orchestrators. If an agent-crew library (e.g. CrewAI) is used, scope it to a single node's internal sub-task loop only — it must never own cross-node routing or bypass the graph's approval/audit points.
- Data: use Pandas/DuckDB only within controlled analysis tools; PostgreSQL remains authoritative. pgvector (co-located in PostgreSQL) is the default vector store; Qdrant is an optional profile for larger/standalone retrieval workloads and remains rebuildable from PostgreSQL-recorded sources.
- Coordination: Redis carries only ephemeral state — event/SSE fan-out and cross-agent notifications. It is never a system of record; nothing is durably readable only from Redis.
- Observability: LLM calls are traced through self-hosted Langfuse only; never send prompts, outputs, or telemetry to a third-party hosted analytics service.
- Infrastructure: Docker Compose must remain usable by a developer on a clean local machine. New services (Redis, pgvector-enabled Postgres, optional Qdrant/Langfuse profiles) must not raise the baseline `docker compose up` cost for a developer who only needs the core stack.

## Workflow and agent safety

- LangGraph state must be JSON-serializable, versioned where needed, bounded in size, and checkpointed at meaningful transitions.
- Add graph paths for success, failure, retry, replan, cancellation, recovery, and Compliance escalation. Bound retries and replans.
- Agents can propose actions but cannot bypass tool policy, RBAC, scope checks, or required approvals. Delegation between agents (e.g. QA requesting an Analyst re-run) always re-enters the graph through the orchestrator/dispatch node — agents never invoke each other's tools directly, even where a message-bus/event notification exists between them.
- A mission's findings must pass both the QA agent (evidentiary support, groundedness/hallucination checks) and the Compliance agent (policy/PII/regulatory review) before the Report agent may assemble a deliverable. Neither gate may be skipped, short-circuited, or merged into a single check without an explicit architecture change.
- Register tools through the allowlisted adapter protocol with Pydantic inputs/outputs, timeout, risk classification, redaction, and audit hooks.
- Never enable arbitrary shell commands, unrestricted filesystem access, unrestricted network egress, or write-capable external integrations by default.

### Sandboxed code execution (Analyst agent)

- Generated Python code is untrusted data. It is never `eval`'d, `exec`'d, or otherwise run inside the API process — it only runs inside the governed sandbox tool adapter.
- The sandbox is network-disabled, resource- and time-bounded, runs as a non-root least-privilege process/container, has no access to the host filesystem beyond a disposable per-execution scratch directory, cannot install arbitrary packages, and is torn down after each run.
- Every execution is logged (script hash, resource usage, exit status, redacted stdout/stderr) and treated as high-risk: approval-gated by default, same as any other high-risk tool.

### Text-to-SQL (Data agent)

- The Data agent's database role is read-only and schema-scoped. Any generated statement that is not a `SELECT` must be rejected before execution, not merely logged afterward.
- Enforce row and time limits on every query; log statement, target schema, row count, and duration for audit.

## Security and data handling

- Authenticate and authorize at every API boundary; enforce workspace ownership in service/repository queries.
- Never commit secrets, real customer data, model credentials, `.env`, or generated local volumes.
- Do not log raw tokens, credentials, or sensitive mission content unless an explicitly reviewed retention policy permits it. Redact before logs, events, model context, sandbox output, and artifacts.
- Audit important state changes, approvals, agent invocations, tool requests/results (including SQL statements and code executions), QA verdicts, Compliance verdicts, and final delivery. Audit entries are append-only.
- Use parameterized database access, validate all external input, enforce payload/time limits, and pin or review dependencies.
- Knowledge ingestion into the retrieval corpus (pgvector/Qdrant) is an explicit, audited pipeline — agents read from it but never write to it directly.

## API, database, and frontend contracts

- Version APIs under `/api/v1`; use Pydantic request/response models and preserve backwards compatibility or explicitly version breaking changes.
- Generate/update API client types from OpenAPI rather than duplicating request types in the frontend.
- Create Alembic migrations for schema changes, including pgvector column/extension changes; do not alter production schema manually.
- Keep UI state feature-local, make loading/error/empty states deliberate, and use accessible semantic controls.

## Quality gate

- Add or update focused tests for behavior changes. Use fake LLMs/tools in automated tests; no CI test may require a downloaded model, a live network call, or a live Langfuse instance.
- New tool classes (retrieval, SQL, sandboxed code execution) ship with their own policy/safety tests (statement allowlisting, resource/network isolation) in addition to behavior tests.
- Run the relevant formatter, linter, type checker, and test suite before handoff. Report commands run and failures honestly.
- Prefer readable code, small modules, named domain concepts, and comments that explain non-obvious constraints rather than restating code.
- Do not make destructive Git operations or delete user files unless the user explicitly requests it.
