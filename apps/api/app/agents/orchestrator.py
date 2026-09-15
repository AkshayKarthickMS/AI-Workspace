from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.events.audit import AuditSink
from app.llm.base import LLMProvider
from app.schemas.agents import AgentRole, Mission, Plan, Task
from app.schemas.planning import DraftPlan

_SYSTEM_PROMPT = (
    "You are the planning manager for an autonomous enterprise AI workforce. "
    "Given a business mission, decide which of the following gathering agents "
    "are needed to accomplish it -- you must choose at least one and may choose "
    "more than one:\n"
    "- research: gather context from the enterprise knowledge base or approved sources\n"
    "- data: answer a structured question against a database via SQL\n"
    "- analyst: analyze a staged tabular dataset (CSV) or run custom analysis code\n"
    "For each agent you choose, write a short task description and any input "
    "parameters it needs (e.g. a `query` for research, a `question` for data, a "
    "`dataset_path` for analyst). Do not invent a QA, compliance, or reporting "
    "step -- those are handled separately. Reply with JSON only."
)


class OrchestratorAgent(BaseAgent[Plan]):
    role = AgentRole.ORCHESTRATOR

    def __init__(self, llm: LLMProvider, audit: AuditSink | None = None) -> None:
        super().__init__(audit)
        self.llm = llm

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> Plan:
        draft = self.llm.complete(
            system=_SYSTEM_PROMPT,
            prompt=self._mission_prompt(mission),
            response_model=DraftPlan,
            run_id=run_id,
            task_id=task_id,
        )

        gathering_tasks = self._build_gathering_tasks(draft)
        qa_task = Task(
            agent=AgentRole.QA,
            description=(
                "Check calculations, evidence coverage, and groundedness for all research "
                "and analysis findings."
            ),
            dependencies=[task.task_id for task in gathering_tasks],
        )
        compliance_task = Task(
            agent=AgentRole.COMPLIANCE,
            description="Review QA-cleared findings for policy, PII, and regulatory concerns.",
            dependencies=[qa_task.task_id],
        )
        report_task = Task(
            agent=AgentRole.REPORT,
            description=(
                "Create an executive report and slide deck using only QA- and "
                "Compliance-cleared findings, with recommendations clearly separated."
            ),
            dependencies=[compliance_task.task_id],
        )

        tasks = [*gathering_tasks, qa_task, compliance_task, report_task]
        return Plan(mission_id=mission.mission_id, rationale=draft.rationale, tasks=tasks)

    @staticmethod
    def _mission_prompt(mission: Mission) -> str:
        lines = [f"Objective: {mission.objective}"]
        if mission.constraints:
            lines.append(f"Constraints: {'; '.join(mission.constraints)}")
        if mission.success_criteria:
            lines.append(f"Success criteria: {'; '.join(mission.success_criteria)}")
        if mission.context:
            lines.append(f"Available context keys: {sorted(mission.context.keys())}")
        return "\n".join(lines)

    @staticmethod
    def _build_gathering_tasks(draft: DraftPlan) -> list[Task]:
        tasks: list[Task] = []
        seen_agents: set[str] = set()
        for draft_task in draft.tasks:
            if draft_task.agent in seen_agents:
                continue
            seen_agents.add(draft_task.agent)
            tasks.append(
                Task(
                    agent=AgentRole(draft_task.agent),
                    description=draft_task.description,
                    input=draft_task.input,
                )
            )
        return tasks
