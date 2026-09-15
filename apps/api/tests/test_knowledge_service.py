"""Knowledge ingestion service tests, using FakeEmbeddingProvider (AGENTS.md
- no CI test may require a live model)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Workspace
from app.models.knowledge import IngestionStatus
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.services.knowledge import ingest_document, list_documents


@pytest.fixture
def session() -> Iterator[Session]:
    # Unlike tests/test_persistence.py, this test genuinely needs
    # knowledge_chunks (ingestion writes to it) -- SQLite accepts the
    # pgvector column loosely typed, same as tests/test_retrieval.py.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db_session:
        yield db_session


def test_ingest_document_creates_a_ready_document(session: Session) -> None:
    workspace = Workspace(name="Acme", slug="acme")
    session.add(workspace)
    session.flush()

    document = ingest_document(
        session,
        workspace_id=workspace.id,
        source_uri="policy://refund-policy",
        text="Refunds are issued within thirty days of purchase for unopened products.",
        embeddings=FakeEmbeddingProvider(dimensions=64),
    )
    session.commit()

    assert document.ingestion_status == IngestionStatus.READY
    assert document.workspace_id == workspace.id

    documents = list_documents(session, workspace_id=workspace.id)
    assert [doc.id for doc in documents] == [document.id]
