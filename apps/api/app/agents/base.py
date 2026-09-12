import logging
from abc import ABC, abstractmethod
from typing import Any, TypeVar
from uuid import UUID

from app.events.audit import AuditEvent, AuditSink
from app.schemas.agents import AgentRole, Mission

logger = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")


class AgentInvocationError(RuntimeError):
    """Raised when an agent cannot produce a validated result."""


class BaseAgent[ResultT](ABC):
    role: AgentRole

    def __init__(self, audit: AuditSink | None = None) -> None:
        self.audit = audit or AuditSink()

    def invoke(
        self,
        mission: Mission,
        run_id: UUID,
        task_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> ResultT:
        self.audit.emit(
            AuditEvent(
                event_type="agent.invocation.started",
                actor=self.role.value,
                mission_id=mission.mission_id,
                run_id=run_id,
                task_id=task_id,
                status="started",
            )
        )
        try:
            result = self.run(mission, run_id, task_id, context or {})
        except Exception as exc:
            logger.exception("agent_failed role=%s run_id=%s", self.role.value, run_id)
            self.audit.emit(
                AuditEvent(
                    event_type="agent.invocation.completed",
                    actor=self.role.value,
                    mission_id=mission.mission_id,
                    run_id=run_id,
                    task_id=task_id,
                    status="failed",
                    metadata={"error": str(exc)[:500]},
                )
            )
            raise AgentInvocationError(f"{self.role.value} failed: {exc}") from exc
        self.audit.emit(
            AuditEvent(
                event_type="agent.invocation.completed",
                actor=self.role.value,
                mission_id=mission.mission_id,
                run_id=run_id,
                task_id=task_id,
                status="completed",
            )
        )
        return result

    @abstractmethod
    def run(
        self, mission: Mission, run_id: UUID, task_id: UUID | None, context: dict[str, Any]
    ) -> ResultT:
        """Execute the role-specific behavior and return a typed result."""
