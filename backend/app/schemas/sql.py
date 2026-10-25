"""Pydantic schemas for standalone SQL syntax and policy validation."""

from pydantic import BaseModel, Field


class SQLValidateRequest(BaseModel):
    """Payload for validating a raw SQL query string against security policies."""

    sql: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Raw SQL statement to parse and validate against security policies",
        examples=["SELECT region, COUNT(*) FROM customers GROUP BY region;"],
    )


class SQLValidateResponse(BaseModel):
    """Validation response indicating whether SQL passes AST security rules."""

    valid: bool = Field(
        ...,
        description="Whether the query passed all security, syntax, and table allowlist checks",
        examples=[True],
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Explanations or policy failure messages if invalid",
        examples=[[]],
    )
    normalized_sql: str | None = Field(
        default=None,
        description="Sanitized and normalized SQL with standard formatting and row limits",
        examples=["SELECT region, COUNT(*) FROM customers GROUP BY region LIMIT 100;"],
    )
