"""Integration tests for global exception handlers, security masking, and request tracing."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_unhandled_exception_returns_500_generic_envelope(client: TestClient) -> None:
    """Verify an induced unhandled exception returns a generic 500 envelope without traceback."""
    response = client.get("/debug/crash")
    assert response.status_code == 500

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An internal server error occurred."
    assert "request_id" in data
    assert response.headers["X-Request-ID"] == data["request_id"]

    # Critical security assertion: No stack trace, file path, or exception class leaked in response
    body_text = response.text.lower()
    assert "traceback" not in body_text
    assert "runtimeerror" not in body_text
    assert "induced unhandled exception" not in body_text
    assert "app/main.py" not in body_text


@pytest.mark.integration
def test_not_found_returns_404_standard_envelope(client: TestClient) -> None:
    """Verify 404 responses return the standard error envelope."""
    response = client.get("/api/v1/nonexistent-route-endpoint")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data
    assert response.headers["X-Request-ID"] == data["request_id"]


@pytest.mark.integration
def test_custom_request_id_header_propagation(client: TestClient) -> None:
    """Verify incoming X-Request-ID header is preserved and propagated to response."""
    custom_id = "test-custom-request-id-998877"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id


@pytest.mark.integration
def test_custom_request_id_in_error_envelope(client: TestClient) -> None:
    """Verify incoming X-Request-ID header is preserved in error envelopes."""
    custom_id = "test-error-request-id-112233"
    response = client.post(
        "/api/v1/query",
        json={"question": "too short"},
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 501
    data = response.json()
    assert data["request_id"] == custom_id
    assert response.headers["X-Request-ID"] == custom_id
