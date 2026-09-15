#!/bin/sh
set -e

# Render (and most PaaS free tiers) assign the listen port via $PORT rather
# than a fixed one; docker-compose.yml's local stack doesn't set $PORT, so
# this still defaults to 8000 for that path.
PORT="${PORT:-8000}"

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
