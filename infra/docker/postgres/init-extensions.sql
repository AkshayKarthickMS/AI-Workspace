-- Runs once via docker-entrypoint-initdb.d on first container init.
-- pgvector is the Day-1 default vector store (see ARCHITECTURE.md §8); Alembic
-- migrations own the actual knowledge_chunks schema, this only guarantees the
-- extension is available to them.
CREATE EXTENSION IF NOT EXISTS vector;
