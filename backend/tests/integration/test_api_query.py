"""Integration tests for POST /api/v1/query endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_query_valid_input_returns_501_envelope(client: TestClient) -> None:
    """Verify valid query returns 501 NOT_IMPLEMENTED envelope with request_id."""
    payload = {
        "question": "What is the total revenue by customer region?",
        "include_explanation": True,
    }
    response = client.post("/api/v1/query", json=payload)
    assert response.status_code == 501

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_IMPLEMENTED"
    assert "Phase 5" in data["error"]["message"]
    assert "request_id" in data
    assert response.headers["X-Request-ID"] == data["request_id"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "invalid_payload,expected_err",
    [
        ({"question": ""}, "too_short"),
        ({"question": "   "}, "too_short"),
        ({"question": "ab"}, "too_short"),
        ({"question": "   ab   "}, "too_short"),
        ({"question": "x" * 501}, "too_long"),
        ({}, "missing"),
    ],
)
def test_query_invalid_input_returns_422_envelope(
    client: TestClient, invalid_payload: dict, expected_err: str
) -> None:
    """Verify blank, too short, too long, or missing questions return 422 standard envelope."""
    response = client.post("/api/v1/query", json=invalid_payload)
    assert response.status_code == 422

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]
    assert "errors" in data["error"]["details"]
    assert len(data["error"]["details"]["errors"]) > 0
    assert "request_id" in data
    assert response.headers["X-Request-ID"] == data["request_id"]
