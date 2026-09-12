# AegisOS Development Rules

## Scope and approach

- Preserve the modular monorepo described in `ARCHITECTURE.md`; do not introduce application code outside its owning module without a clear reason.
- Prefer the smallest production-quality change that satisfies the requested behavior. Do not add distributed infrastructure, external SaaS dependencies, or autonomous side-effect tools without explicit approval.
- Before editing, inspect nearby code, existing tests, and current Git changes. Preserve unrelated work.
- Update architecture/docs when a change alters a public contract, persistent schema, security boundary, workflow, or local setup.

## Technology boundaries

- Web: Next.js, TypeScript, Tailwind, and shadcn/ui. Keep business decisions in the backend.
- API: Python, FastAPI, Pydantic, LangGraph, PostgreSQL. Use explicit dependencies, typed schemas, and Alembic migrations.
- AI: access local Ollama only through a provider interface. Require structured, validated outputs; never treat generated text as executable instructions.
- Data: use Pandas/DuckDB only within controlled analysis tools; PostgreSQL remains authoritative and Qdrant remains rebuildable.
- Infrastructure: Docker Compose must remain usable by a developer on a clean local machine.

## Workflow and agent safety

- LangGraph state must be JSON-serializable, versioned where needed, bounded in size, and checkpointed at meaningful transitions.
- Add graph paths for success, failure, retry, cancellation, and recovery. Bound retries and replans.
- Agents can propose actions but cannot bypass tool policy, RBAC, scope checks, or required approvals.
- Register tools through the allowlisted adapter protocol with Pydantic inputs/outputs, timeout, risk classification, redaction, and audit hooks.
- Never enable arbitrary shell commands, unrestricted filesystem access, arbitrary network egress, or write-capable external integrations by default.

## Security and data handling

- Authenticate and authorize at every API boundary; enforce workspace ownership in service/repository queries.
- Never commit secrets, real customer data, model credentials, `.env`, or generated local volumes.
- Do not log raw tokens, credentials, or sensitive mission content unless an explicitly reviewed retention policy permits it. Redact before logs, events, model context, and artifacts.
- Audit important state changes, approvals, agent invocations, tool requests/results, verification, and final delivery. Audit entries are append-only.
- Use parameterized database access, validate all external input, enforce payload/time limits, and pin or review dependencies.

## API, database, and frontend contracts

- Version APIs under `/api/v1`; use Pydantic request/response models and preserve backwards compatibility or explicitly version breaking changes.
- Generate/update API client types from OpenAPI rather than duplicating request types in the frontend.
- Create Alembic migrations for schema changes; do not alter production schema manually.
- Keep UI state feature-local, make loading/error/empty states deliberate, and use accessible semantic controls.

## Quality gate

- Add or update focused tests for behavior changes. Use fake LLMs/tools in automated tests; no CI test may require a downloaded model.
- Run the relevant formatter, linter, type checker, and test suite before handoff. Report commands run and failures honestly.
- Prefer readable code, small modules, named domain concepts, and comments that explain non-obvious constraints rather than restating code.
- Do not make destructive Git operations or delete user files unless the user explicitly requests it.
