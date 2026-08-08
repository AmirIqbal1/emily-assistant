from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoint() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "emily-core",
        "version": "0.2.0",
    }


def test_security_headers_are_set() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
