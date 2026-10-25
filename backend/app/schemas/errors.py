"""Pydantic schemas for standardized error envelopes."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error object within the standard error envelope."""

    code: str = Field(
        ...,
        description="Machine-readable uppercase error code",
        examples=["VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_SERVER_ERROR"],
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the error",
        examples=["Request validation failed.", "Resource not found."],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured details, parameters, or field errors",
    )


class ErrorEnvelope(BaseModel):
    """Standard top-level error response envelope returned on all non-2xx statuses."""

    error: ErrorDetail
    request_id: str = Field(
        ...,
        description="Traceable request identifier",
        examples=["req_01h8v1b5p7k"],
    )
