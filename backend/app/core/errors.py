"""Application error hierarchy and global exception handlers.

Ensures all errors return a uniform, standardized JSON error envelope:
{
    "error": {
        "code": "...",
        "message": "...",
        "details": {...}  # optional
    },
    "request_id": "..."
}

Never leaks stack traces or sensitive database details to clients.
"""

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("app.core.errors")


class AppError(Exception):
    """Base application exception for all domain and security errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        http_status: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.details = details


class ValidationRejected(AppError):
    """Raised when question or SQL fails AST/security validation rules."""

    def __init__(
        self,
        message: str = "Input rejected by validation policy.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_REJECTED",
            http_status=400,
            details=details,
        )


class UnsupportedQuestion(AppError):
    """Raised when a question is outside the database domain scope."""

    def __init__(
        self,
        message: str = "Question is not supported by the database domain.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNSUPPORTED_QUESTION",
            http_status=400,
            details=details,
        )


class LLMUnavailable(AppError):
    """Raised when the LLM provider is unreachable or returns an error."""

    def __init__(
        self,
        message: str = "LLM provider is currently unavailable.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LLM_UNAVAILABLE",
            http_status=503,
            details=details,
        )


class DatabaseUnavailable(AppError):
    """Raised when PostgreSQL connection fails or times out."""

    def __init__(
        self,
        message: str = "Database service is currently unavailable.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="DATABASE_UNAVAILABLE",
            http_status=503,
            details=details,
        )


class QueryTimeout(AppError):
    """Raised when a database query exceeds the statement timeout."""

    def __init__(
        self,
        message: str = "Database query execution exceeded statement timeout.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="QUERY_TIMEOUT",
            http_status=504,
            details=details,
        )


class NotFound(AppError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            http_status=404,
            details=details,
        )


class InternalError(AppError):
    """Raised for unexpected internal errors."""

    def __init__(
        self,
        message: str = "An internal error occurred.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INTERNAL_ERROR",
            http_status=500,
            details=details,
        )


class FeatureNotImplemented(AppError):
    """Raised for documented pipeline stages pending future implementation phases."""

    def __init__(
        self,
        message: str = "Endpoint or feature is not yet implemented.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NOT_IMPLEMENTED",
            http_status=501,
            details=details,
        )


def _get_request_id(request: Request) -> str:
    """Extract or generate a request ID for error responses."""
    return (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or f"req_{uuid.uuid4().hex[:12]}"
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle all domain AppError exceptions with standard envelope."""
    request_id = _get_request_id(request)
    error_payload: dict[str, Any] = {
        "code": exc.code,
        "message": exc.message,
    }
    if exc.details is not None:
        error_payload["details"] = exc.details

    return JSONResponse(
        status_code=exc.http_status,
        content={"error": error_payload, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic request validation errors (422) with standard envelope."""
    request_id = _get_request_id(request)
    # Sanitize validation errors to clean JSON
    errors_list = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", [])]
        msg = err.get("msg", "Validation error")
        typ = err.get("type", "value_error")
        errors_list.append({"location": loc, "message": msg, "type": typ})

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": {"errors": errors_list},
            },
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle generic Starlette/FastAPI HTTPExceptions with standard envelope."""
    request_id = _get_request_id(request)
    status_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        500: "INTERNAL_SERVER_ERROR",
        501: "NOT_IMPLEMENTED",
        503: "SERVICE_UNAVAILABLE",
    }
    code = status_code_map.get(exc.status_code, "HTTP_ERROR")

    # If detail is already a dict containing code/message, adopt it
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", "An HTTP error occurred.")
        code = exc.detail.get("code", code)
        details = exc.detail.get("details")
    else:
        message = str(exc.detail) if exc.detail else "An HTTP error occurred."
        details = None

    error_payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error_payload["details"] = details

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_payload, "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled server exceptions.

    Logs the full exception server-side with request_id and returns a generic 500
    without leaking internal paths, SQL queries, or stack traces.
    """
    request_id = _get_request_id(request)
    logger.exception(
        "Unhandled server exception during request processing [request_id=%s]: %s",
        request_id,
        exc,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
            },
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all custom error handlers with the FastAPI application."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
