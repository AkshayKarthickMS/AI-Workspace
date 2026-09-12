from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_service_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {
        "status": "ok",
        "service": "aegisos-api",
        "version": "0.1.0",
        "environment": "development",
    }
