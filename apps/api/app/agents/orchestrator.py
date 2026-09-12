from typing import Any
from uuid import UUID

from app.agents.base import BaseAgent
from app.schemas.agents import AgentRole, Mission, Plan, Task


class OrchestratorAgent(BaseAgent[Plan]):
    role = AgentRole.ORCHESTRATOR

    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> Plan:
        tasks = [
            Task(
                agent=AgentRole.RESEARCH,
                description=(
                    "Collect approved external or user-provided evidence relevant to the mission."
                ),
                input={"query": mission.objective},
            ),
            Task(
                agent=AgentRole.DATA_ANALYST,
                description=(
                    "Analyze the supplied dataset and calculate evidence-backed statistics and anomalies."
                ),
                input={"dataset_path": mission.context.get("dataset_path", "")},
            ),
        ]
        verification_task = Task(
            agent=AgentRole.VERIFICATION,
            description=(
                "Check calculations, evidence coverage, and support for all research and analysis findings."
            ),
            dependencies=[task.task_id for task in tasks],
        )
        tasks.append(verification_task)
        tasks.append(
            Task(
                agent=AgentRole.REPORT,
                description=(
                    "Create an executive report using only verified findings and clearly separated recommendations."
                ),
                dependencies=[verification_task.task_id],
            )
        )
        return Plan(
            mission_id=mission.mission_id,
            rationale="Run independent evidence collection and analysis, verify both, then report.",
            tasks=tasks,
        )
