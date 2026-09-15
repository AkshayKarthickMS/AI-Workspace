"""Data agent: LLM-drafted SQL executed through the validated, read-only tool
(ARCHITECTURE.md section 7, section 10)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.agents.base import AgentInvocationError
from app.agents.data import DataAgent
from app.events.audit import AuditSink
from app.llm.fake import FakeLLMProvider
from app.schemas.agents import Mission
from app.tools.sql_query import TextToSqlTool

MISSION = Mission(objective="How many widgets were sold?")


@pytest.fixture
def session_factory() -> object:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sales (id INTEGER PRIMARY KEY, widgets INTEGER)"))
        conn.execute(text("INSERT INTO sales (widgets) VALUES (3), (5)"))
    factory = sessionmaker(bind=engine)

    @contextmanager
    def scope() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    return scope


def test_data_agent_executes_llm_drafted_select(session_factory) -> None:  # type: ignore[no-untyped-def]
    def llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        return response_model(statement="SELECT widgets FROM sales")

    agent = DataAgent(
        FakeLLMProvider(factory=llm_factory), TextToSqlTool(session_factory), AuditSink()
    )
    result = agent.invoke(
        MISSION, run_id=MISSION.mission_id, context={"question": MISSION.objective}
    )

    assert result.status == "success"
    assert result.output["columns"] == ["widgets"]
    assert result.output["rows"] == [{"widgets": 3}, {"widgets": 5}]
    assert result.findings[0].metrics["row_count"] == 2


def test_data_agent_rejects_llm_drafted_non_select(session_factory) -> None:  # type: ignore[no-untyped-def]
    def llm_factory(response_model: type[BaseModel], system: str, prompt: str) -> BaseModel:
        return response_model(statement="DELETE FROM sales")

    agent = DataAgent(
        FakeLLMProvider(factory=llm_factory), TextToSqlTool(session_factory), AuditSink()
    )
    with pytest.raises(AgentInvocationError):
        agent.invoke(MISSION, run_id=MISSION.mission_id, context={"question": MISSION.objective})

    with session_factory() as session:
        count = session.execute(text("SELECT COUNT(*) FROM sales")).scalar_one()
    assert count == 2  # nothing was deleted
