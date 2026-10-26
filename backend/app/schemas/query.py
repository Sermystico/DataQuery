"""Pydantic schemas for query submission and response."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ChartHint(BaseModel):
    """Recommended visualization layout for query results."""

    type: Literal["bar", "line", "none"] = Field(
        ...,
        description="Recommended chart presentation style: 'bar', 'line', or 'none'",
        examples=["bar"],
    )
    x_key: str | None = Field(
        default=None,
        description="Column name for the independent variable / X axis",
        examples=["region"],
    )
    y_key: str | None = Field(
        default=None,
        description="Column name for the dependent variable / Y axis",
        examples=["total_revenue"],
    )
    title: str | None = Field(
        default=None,
        description="Suggested chart title",
        examples=["Revenue by Customer Region"],
    )

    @property
    def chart_type(self) -> str:
        return self.type

    @property
    def x_column(self) -> str | None:
        return self.x_key

    @property
    def y_column(self) -> str | None:
        return self.y_key

    def __bool__(self) -> bool:
        return self.type != "none"


class QueryRequest(BaseModel):
    """Natural language business query request payload."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language business question (3 to 500 characters)",
        examples=["What is the total revenue by customer region?"],
    )
    include_explanation: bool = Field(
        default=True,
        description="Whether to generate a natural language explanation alongside SQL results",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Strip whitespace and ensure non-blank with at least 3 characters."""
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Question must contain at least 3 non-whitespace characters.")
        if len(cleaned) > 500:
            raise ValueError("Question must not exceed 500 characters.")
        return cleaned


class QueryResponse(BaseModel):
    """Standard response model for natural language analytics queries."""

    status: Literal["success", "unsupported", "rejected"] = Field(
        ...,
        description="Pipeline processing status",
        examples=["success"],
    )
    question: str = Field(
        ...,
        description="Original user question",
        examples=["What is the total revenue by customer region?"],
    )
    answer: str | None = Field(
        default=None,
        description="Synthesized natural language answer or explanation",
        examples=["The total revenue by customer region is..."],
    )
    sql: str | None = Field(
        default=None,
        description="Validated SQL statement executed against read-only database",
        examples=["SELECT region, SUM(quantity * unit_price) AS total_revenue ..."],
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Ordered list of column names in the result set",
        examples=[["region", "total_revenue"]],
    )
    rows: list[list[Any]] = Field(
        default_factory=list,
        description="Tabular result rows matching column order",
        examples=[[["North America", 142500.0], ["EMEA", 98230.5]]],
    )
    row_count: int = Field(
        default=0,
        description="Number of rows returned",
        examples=[2],
    )
    truncated: bool = Field(
        default=False,
        description="Whether the result set was capped by the MAX_RESULT_ROWS limit",
    )
    chart_hint: ChartHint | None = Field(
        default=None,
        description="Visual presentation guidance for frontend charting",
    )
    explanation_source: Literal["llm", "fallback", "none"] = Field(
        default="none",
        description="Source of the explanation text",
    )
    request_id: str = Field(
        ...,
        description="Traceable request identifier",
        examples=["req_01h8v1b5p7k"],
    )
    history_id: int | None = Field(
        default=None,
        description="Database audit log ID for this query execution",
        examples=[1],
    )
    rejection_reasons: list[str] = Field(
        default_factory=list,
        description="Detailed reasons if the query was unsupported or rejected by policy",
        examples=[["Query references forbidden table 'pg_shadow'."]],
    )
