"""Versioned product API (ARCHITECTURE.md section 9). Mounted under
``/api/v1`` by ``app.main``; ``GET /health`` is the sole unversioned route."""

from fastapi import APIRouter

from app.api.v1 import artifacts, audit, datasets, knowledge, missions, runs, workspaces

router = APIRouter(prefix="/api/v1")
router.include_router(workspaces.router)
router.include_router(missions.router)
router.include_router(runs.router)
router.include_router(artifacts.router)
router.include_router(artifacts.content_router)
router.include_router(audit.router)
router.include_router(knowledge.router)
router.include_router(datasets.router)

__all__ = ["router"]
