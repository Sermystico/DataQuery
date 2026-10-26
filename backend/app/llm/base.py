"""Base models and protocols for LLM provider integrations in DataQuery."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator


class SQLGeneration(BaseModel):
    """Structured output contract for natural language to SQL translation."""

    supported: bool = Field(
        ...,
        description="Whether the business question can be answered by the analytical database schema.",
    )
    sql: str | None = Field(
        default=None,
        description="The generated SQL query if supported, or None if unsupported.",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation of why the question is unsupported, or None if supported.",
    )

    @model_validator(mode="after")
    def validate_supported_contract(self) -> "SQLGeneration":
        """Ensure supported queries include non-empty SQL, and unsupported queries include a reason."""
        if self.supported:
            if not self.sql or not self.sql.strip():
                raise ValueError("When supported is True, 'sql' must be provided and non-empty.")
            self.sql = self.sql.strip()
        else:
            if not self.reason or not self.reason.strip():
                raise ValueError("When supported is False, 'reason' must be provided and non-empty.")
            self.reason = self.reason.strip()
        return self


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the required capabilities of an LLM provider."""

    def generate_sql(self, question: str, schema_context: str) -> SQLGeneration:
        """Translate a natural language question into structured SQL generation output."""
        ...

    def explain(
        self,
        question: str,
        columns: list[str],
        rows: list[list[Any]],
        sql: str,
    ) -> str:
        """Generate a natural language explanation of query results (Implemented in Phase 6)."""
        ...
