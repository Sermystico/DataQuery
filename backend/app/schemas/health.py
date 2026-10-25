"""Pydantic schemas for health and readiness checks."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """System health check response."""

    status: str = Field(..., description="Overall health state", examples=["ok"])
    database: str = Field(
        ...,
        description="Database connectivity status verified via SELECT 1 against dq_readonly",
        examples=["connected"],
    )
    version: str = Field(default="1.0.0", description="Application semantic version")
    as_of_date: str = Field(
        ...,
        description="Canonical analytics reference date in effect",
        examples=["2024-11-01T00:00:00Z"],
    )
