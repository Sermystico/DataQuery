"""Integration tests for the /health endpoint and database probe."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import engines


@pytest.mark.integration
def test_health_ok(client: TestClient) -> None:
    """Verify GET /health returns 200, status ok, and database connected."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["version"] == "1.0.0"
    assert "as_of_date" in data

    # Verify X-Request-ID and X-Process-Time headers
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


@pytest.mark.integration
def test_api_v1_health_ok(client: TestClient) -> None:
    """Verify GET /api/v1/health returns 200 with identical structure."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.integration
def test_health_503_when_database_down(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify health endpoint returns 503 with standard envelope when DB engine points to bad host."""

    def mock_bad_host_connect(*args: object, **kwargs: object) -> None:
        raise OperationalError(
            "could not connect to server at 'bad_host': connection refused",
            params=None,
            orig=Exception("Connection refused"),
        )

    # Monkeypatch the readonly engine connect method to simulate bad host failure
    monkeypatch.setattr(engines.readonly_engine, "connect", mock_bad_host_connect)

    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()

    # Standard error envelope structure
    assert "error" in data
    assert data["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert (
        "database" in data["error"]["message"].lower()
        or "connection" in data["error"]["message"].lower()
    )
    assert "request_id" in data
    assert response.headers["X-Request-ID"] == data["request_id"]
