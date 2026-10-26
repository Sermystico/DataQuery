"""Deterministic Mock LLM provider with failure-injection modes and golden query registry."""

import re
from typing import Any, Literal

from app.core.errors import LLMUnavailable
from app.llm.base import SQLGeneration
from app.llm.golden_queries import GOLDEN_QUERIES

MockMode = Literal["normal", "raise", "garbage", "unsafe_sql", "unsupported", "raise_explain"]


def normalize_query_text(text: str) -> str:
    """Normalize whitespace and lowercase for canonical question matching."""
    return re.sub(r"\s+", " ", text.strip().lower())


class MockLLMProvider:
    """Deterministic LLM provider mapping canonical business questions to verified SQL."""

    def __init__(self, mode: MockMode = "normal", explain_fail: bool = False) -> None:
        self.mode = mode
        self.explain_fail = explain_fail
        # Build normalized lookup dictionary
        self._registry: dict[str, str] = {
            normalize_query_text(item.question): item.sql for item in GOLDEN_QUERIES
        }

    def generate_sql(self, question: str, schema_context: str | None = None) -> SQLGeneration:
        """Generate deterministic SQL based on the question and configured failure mode."""
        # 1. Failure-injection modes
        if self.mode == "raise":
            raise LLMUnavailable(
                message="Simulated upstream LLM provider failure.",
                details={"mode": "raise", "provider": "mock"},
            )

        if self.mode == "garbage":
            return SQLGeneration(
                supported=True,
                sql="SELECT FROM WHERE GIBBERISH %%% SYNTAX ERROR",
            )

        if self.mode == "unsafe_sql":
            return SQLGeneration(
                supported=True,
                sql="DROP TABLE orders; SELECT * FROM pg_shadow;",
            )

        if self.mode == "unsupported":
            return SQLGeneration(
                supported=False,
                reason="Question forced into unsupported mode by test configuration.",
            )

        # 2. Normal mode: canonical question lookup
        normalized = normalize_query_text(question)

        # Explicitly check for prompt injections or adversarial overrides
        if any(
            phrase in normalized
            for phrase in [
                "ignore your rules",
                "ignore all previous",
                "drop table",
                "delete from",
                "alter table",
                "hack",
                "jailbreak",
            ]
        ):
            return SQLGeneration(
                supported=False,
                reason="Adversarial prompt or policy override attempt detected.",
            )

        if normalized in self._registry:
            return SQLGeneration(
                supported=True,
                sql=self._registry[normalized],
            )

        # Unknown question
        return SQLGeneration(
            supported=False,
            reason=(
                "The requested question could not be mapped to any canonical "
                "query pattern in the mock analytical registry."
            ),
        )

    def explain(
        self,
        question: str,
        columns: list[str],
        rows: list[list[Any]],
        row_count: int | None = None,
        sql: str | None = None,
    ) -> str:
        """Generate deterministic plain-English summary from actual returned data."""
        if self.mode == "raise_explain" or self.explain_fail:
            raise LLMUnavailable(
                message="Simulated upstream explanation failure.",
                details={"mode": "raise_explain", "provider": "mock"},
            )

        total_rows = row_count if row_count is not None else len(rows)
        if total_rows == 0:
            return "No rows matched this question."

        if total_rows == 1 and len(columns) == 1:
            col_name = columns[0].replace("_", " ")
            return f"The calculated {col_name} is {rows[0][0]}."

        if total_rows == 1 and len(columns) > 1:
            parts = [f"{c.replace('_', ' ')}: {rows[0][i]}" for i, c in enumerate(columns)]
            return f"The result is {', '.join(parts)}."

        # Multiple rows
        col0 = columns[0].replace("_", " ")
        top_val = rows[0][0]
        val_str = f" with {columns[1].replace('_', ' ')} {rows[0][1]}" if len(columns) > 1 else ""
        return (
            f"The query returned {total_rows} records. "
            f"The top result is {top_val} for {col0}{val_str}."
        )
