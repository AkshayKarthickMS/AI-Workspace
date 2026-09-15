"""Ingestion + hybrid search, end to end, over a throwaway SQLite DB using
FakeEmbeddingProvider -- see tests/test_persistence.py for why KnowledgeChunk
(pgvector-only) is exercised this way rather than against real Postgres."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.repositories import KnowledgeChunkRepository, KnowledgeDocumentRepository
from app.db.repositories.identity import WorkspaceRepository
from app.models import Base, Workspace
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.retrieval.ingestion import KnowledgeIngestionService
from app.retrieval.search import HybridSearchService
from app.tools.research import ControlledResearchTool


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


def _seed_workspace(session: Session) -> Workspace:
    workspace = WorkspaceRepository(session).add(Workspace(name="Acme", slug="acme"))
    session.commit()
    return workspace


def test_ingest_then_search_finds_relevant_chunk(session: Session) -> None:
    workspace = _seed_workspace(session)
    embeddings = FakeEmbeddingProvider(dimensions=64)
    ingestion = KnowledgeIngestionService(embeddings=embeddings, chunk_size=200, chunk_overlap=0)

    ingestion.ingest(
        document_repository=KnowledgeDocumentRepository(session),
        chunk_repository=KnowledgeChunkRepository(session),
        workspace_id=workspace.id,
        source_uri="policy://refund-policy",
        text=(
            "Refunds are issued within thirty days of purchase for unopened products. "
            "Shipping costs are non-refundable under any circumstances."
        ),
    )
    ingestion.ingest(
        document_repository=KnowledgeDocumentRepository(session),
        chunk_repository=KnowledgeChunkRepository(session),
        workspace_id=workspace.id,
        source_uri="policy://vacation-policy",
        text="Employees accrue fifteen vacation days per year, prorated for new hires.",
    )
    session.commit()

    search = HybridSearchService(session=session, embeddings=embeddings)
    results = search.search(workspace_id=workspace.id, query="refund shipping policy", limit=3)

    assert results
    assert "Refunds" in results[0].text
    assert results[0].score > 0


def test_search_is_workspace_scoped(session: Session) -> None:
    workspace_a = _seed_workspace(session)
    workspace_b = WorkspaceRepository(session).add(Workspace(name="Other", slug="other"))
    session.commit()

    embeddings = FakeEmbeddingProvider(dimensions=64)
    ingestion = KnowledgeIngestionService(embeddings=embeddings)
    ingestion.ingest(
        document_repository=KnowledgeDocumentRepository(session),
        chunk_repository=KnowledgeChunkRepository(session),
        workspace_id=workspace_b.id,
        source_uri="policy://other-workspace",
        text="This document belongs to a different workspace entirely.",
    )
    session.commit()

    search = HybridSearchService(session=session, embeddings=embeddings)
    results = search.search(workspace_id=workspace_a.id, query="different workspace", limit=3)

    assert results == []


def test_controlled_research_tool_merges_static_and_retrieved_evidence(session: Session) -> None:
    workspace = _seed_workspace(session)
    embeddings = FakeEmbeddingProvider(dimensions=64)
    ingestion = KnowledgeIngestionService(embeddings=embeddings)
    ingestion.ingest(
        document_repository=KnowledgeDocumentRepository(session),
        chunk_repository=KnowledgeChunkRepository(session),
        workspace_id=workspace.id,
        source_uri="policy://refund-policy",
        text="Refunds are issued within thirty days of purchase.",
    )
    session.commit()

    search = HybridSearchService(session=session, embeddings=embeddings)
    tool = ControlledResearchTool(retrieval=search, workspace_id=workspace.id)

    evidence = tool.search("refund policy")

    assert evidence
    assert evidence[0].source_type == "document"
    assert evidence[0].source == "policy://refund-policy"


def test_controlled_research_tool_without_retrieval_is_unchanged() -> None:
    tool = ControlledResearchTool()
    assert tool.search("anything") == []
