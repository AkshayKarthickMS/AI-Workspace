from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.llm.base import LLMProvider
from app.schemas.agents import AgentResult, AgentRole, Evidence, Finding, Mission
from app.schemas.data_queries import DataQueryResult
from app.tools.sql_query import TextToSqlTool


class _SqlDraft(BaseModel):
    statement: str = Field(min_length=1, max_length=4000)


class DataAgent(BaseAgent[AgentResult]):
    """Text-to-SQL agent: answers a structured question via a single
    LLM-drafted, read-only SELECT (ARCHITECTURE.md section 7)."""

    role = AgentRole.DATA

    def __init__(
        self, llm: LLMProvider, sql_tool: TextToSqlTool, audit: AuditSink | None = None
    ) -> None:
        super().__init__(audit)
        self.llm = llm
        self.sql_tool = sql_tool

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> AgentResult:
        question = str(context.get("question", mission.objective))
        target_schema = context.get("target_schema")

        draft = self.llm.complete(
            system=(
                "You write a single read-only PostgreSQL SELECT statement that answers the "
                "user's question against the available schema. Reply with JSON only. Never "
                "write INSERT, UPDATE, DELETE, or any DDL statement."
            ),
            prompt=(
                f"Question: {question}\n"
                f"Target schema hint: {target_schema or 'none provided'}\n"
                "Write the SELECT statement that answers this question."
            ),
            response_model=_SqlDraft,
            run_id=run_id,
            task_id=task_id,
        )

        result: DataQueryResult = self.sql_tool.execute(draft.statement)
        evidence = [
            Evidence(
                source="database",
                source_type="dataset",
                locator=result.statement[:200],
                excerpt=f"Query returned {result.row_count} row(s).",
                metadata={"row_count": result.row_count},
            )
        ]
        findings = [
            Finding(
                statement=f"The query returned {result.row_count} row(s) for: {question}",
                category="fact",
                confidence=0.9 if result.row_count else 0.5,
                evidence=evidence,
                metrics={"row_count": result.row_count},
            )
        ]
        return AgentResult(
            agent=self.role,
            status="success",
            findings=findings,
            evidence=evidence,
            output={
                "statement": result.statement,
                "columns": result.columns,
                "rows": result.rows,
            },
        )
