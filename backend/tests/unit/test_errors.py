"""Unit tests for typed AppErrors and global HTTP exception handlers."""

import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.core.errors import (
    AppError,
    DatabaseUnavailable,
    FeatureNotImplemented,
    InternalError,
    LLMUnavailable,
    NotFound,
    QueryTimeout,
    UnsupportedQuestion,
    ValidationRejected,
    http_exception_handler,
)


@pytest.mark.unit
def test_typed_app_errors_instantiation_and_defaults() -> None:
    """Verify all custom AppError subclasses set appropriate codes and statuses."""
    # ValidationRejected
    vr = ValidationRejected()
    assert vr.code == "VALIDATION_REJECTED"
    assert vr.http_status == 400
    assert "rejected" in vr.message.lower()

    # UnsupportedQuestion
    uq = UnsupportedQuestion()
    assert uq.code == "UNSUPPORTED_QUESTION"
    assert uq.http_status == 400

    # InternalError
    ie = InternalError()
    assert ie.code == "INTERNAL_ERROR"
    assert ie.http_status == 500

    # FeatureNotImplemented
    fni = FeatureNotImplemented()
    assert fni.code == "NOT_IMPLEMENTED"
    assert fni.http_status == 501

    # LLMUnavailable
    llm = LLMUnavailable()
    assert llm.code == "LLM_UNAVAILABLE"
    assert llm.http_status == 503

    # DatabaseUnavailable
    db = DatabaseUnavailable()
    assert db.code == "DATABASE_UNAVAILABLE"
    assert db.http_status == 503

    # QueryTimeout
    qt = QueryTimeout()
    assert qt.code == "QUERY_TIMEOUT"
    assert qt.http_status == 504

    # NotFound
    nf = NotFound()
    assert nf.code == "NOT_FOUND"
    assert nf.http_status == 404

    # AppError base properties
    ae = AppError("Custom message", code="CUSTOM", http_status=418, details={"k": "v"})
    assert ae.message == "Custom message"
    assert ae.code == "CUSTOM"
    assert ae.http_status == 418
    assert ae.details == {"k": "v"}


@pytest.mark.anyio
async def test_app_error_handler_response() -> None:
    """Verify app_error_handler creates standard JSONResponse with details."""
    from app.core.errors import app_error_handler

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/test-app-error",
        "headers": [(b"x-request-id", b"req_ae_test_456")],
    }
    request = Request(scope)
    exc = AppError("Something went wrong", code="CUSTOM_CODE", http_status=400, details={"ctx": "test"})

    response = await app_error_handler(request, exc)
    assert response.status_code == 400

    import json
    data = json.loads(response.body.decode("utf-8"))
    assert data["error"]["code"] == "CUSTOM_CODE"
    assert data["error"]["message"] == "Something went wrong"
    assert data["error"]["details"] == {"ctx": "test"}
    assert data["request_id"] == "req_ae_test_456"


@pytest.mark.anyio
async def test_http_exception_handler_with_dict_detail() -> None:
    """Verify http_exception_handler formats dictionary detail into standard error envelope."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [(b"x-request-id", b"req_dict_test_123")],
    }
    request = Request(scope)

    exc = HTTPException(
        status_code=400,
        detail={
            "message": "Custom error occurred.",
            "code": "CUSTOM_ERROR_CODE",
            "details": {"key": "val"},
        },
    )

    response = await http_exception_handler(request, exc)
    assert response.status_code == 400

    import json
    data = json.loads(response.body.decode("utf-8"))
    assert data["error"]["code"] == "CUSTOM_ERROR_CODE"
    assert data["error"]["message"] == "Custom error occurred."
    assert data["error"]["details"] == {"key": "val"}
    assert data["request_id"] == "req_dict_test_123"
