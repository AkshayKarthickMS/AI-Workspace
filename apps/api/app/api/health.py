from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
def get_health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service="aegisos-api",
        version=settings.app_version,
        environment=settings.environment,
    )
