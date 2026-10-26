"""Pydantic schemas for query execution history."""

from datetime import datetime

from pydantic import BaseModel, Field


class QueryHistoryItem(BaseModel):
    """Historical record of an analytics query execution."""

    id: int = Field(..., description="Unique history record identifier", examples=[1])
    request_id: str = Field(
        ..., description="Traceable request identifier", examples=["req_01h8v1b5p7k"]
    )
    created_at: datetime = Field(..., description="Timestamp when the query was received")
    question: str = Field(
        ...,
        description="Original user natural language question",
        examples=["Total revenue by region?"],
    )
    status: str = Field(
        ...,
        description="Execution status: 'success', 'unsupported', 'rejected', or 'error'",
        examples=["success"],
    )
    sql: str | None = Field(default=None, description="Executed or rejected SQL statement")
    row_count: int | None = Field(
        default=None, description="Number of rows returned for successful executions"
    )
    error_code: str | None = Field(
        default=None, description="High-level error code if the query failed or was rejected"
    )
    duration_ms: float | None = Field(
        default=None, description="Total pipeline latency in milliseconds"
    )


class HistoryResponse(BaseModel):
    """Paginated list of historical query executions."""

    items: list[QueryHistoryItem] = Field(
        default_factory=list, description="Historical query execution records"
    )
    total: int = Field(..., description="Total number of query history records matching filters")
    limit: int = Field(..., description="Maximum records returned in this page")
    offset: int = Field(..., description="Number of records skipped")


# Aliases for backward compatibility
HistoryItem = QueryHistoryItem
HistoryListResponse = HistoryResponse
