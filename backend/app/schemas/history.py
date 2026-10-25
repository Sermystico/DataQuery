"""Pydantic schemas for query execution history and audit logs."""

from pydantic import BaseModel, Field


class HistoryItem(BaseModel):
    """A single record from the query execution audit log."""

    id: str = Field(..., description="Unique query execution identifier", examples=["qry_01h8v1b5p7k"])
    question: str = Field(..., description="Original user natural language question")
    sql_preview: str | None = Field(
        default=None,
        description="Truncated preview of the generated SQL",
    )
    status: str = Field(
        ...,
        description="Query lifecycle status: SUCCESS, VALIDATION_ERROR, DB_ERROR",
        examples=["SUCCESS"],
    )
    execution_time_ms: int | None = Field(
        default=None,
        description="Total database execution duration in milliseconds",
        examples=[45],
    )
    row_count: int | None = Field(
        default=None,
        description="Number of rows returned by the query",
        examples=[5],
    )
    created_at: str = Field(
        ...,
        description="ISO-8601 execution timestamp",
        examples=["2026-10-25T11:45:00Z"],
    )


class HistoryListResponse(BaseModel):
    """Paginated list of query history records."""

    items: list[HistoryItem] = Field(default_factory=list, description="Page of history items")
    limit: int = Field(default=20, description="Max items per page")
    offset: int = Field(default=0, description="Starting offset index")
    total: int = Field(default=0, description="Total history records available")
