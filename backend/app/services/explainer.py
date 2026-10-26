"""Analytical query explanation service for DataQuery.

Generates concise, human-readable explanations based EXCLUSIVELY on actual
returned data rows. Never passes SQL, credentials, environment variables, or
internal exceptions to LLM providers.
"""

from typing import Any, Literal

from app.core.logging import get_logger
from app.llm.base import LLMProvider

logger = get_logger("app.services.explainer")

ExplanationSource = Literal["llm", "fallback", "none"]


def build_fallback_summary(
    columns: list[str],
    rows: list[list[Any]],
    row_count: int,
) -> str:
    """Build a deterministic summary from actual data when the LLM is bypassed or fails."""
    if row_count == 0 or not rows:
        return "No rows matched this question."

    if row_count == 1 and len(columns) == 1:
        col_label = columns[0].replace("_", " ")
        return f"The calculated {col_label} is {rows[0][0]}."

    if row_count == 1:
        pairs = [f"{c.replace('_', ' ')}: {rows[0][i]}" for i, c in enumerate(columns)]
        return f"The query returned 1 row: {', '.join(pairs)}."

    # Multiple rows: report total count and top result row
    top_pairs = [f"{c.replace('_', ' ')}: {rows[0][i]}" for i, c in enumerate(columns)]
    return f"The query returned {row_count} rows. Top result: {', '.join(top_pairs)}."


def generate_explanation(
    question: str,
    columns: list[str],
    rows: list[list[Any]],
    row_count: int,
    provider: LLMProvider,
    include_explanation: bool = True,
) -> tuple[str | None, ExplanationSource]:
    """Generate an explanation adhering strictly to analytical data results.

    Invariants:
    1. If include_explanation is False, returns (None, 'none').
    2. Empty result sets NEVER call the LLM provider; they return a deterministic
       'No rows matched this question.' with source 'fallback'.
    3. At most the first 20 rows and total row_count are passed to the provider.
       SQL and internal credentials are NEVER passed.
    4. If the provider fails or times out, a deterministic fallback summary is
       generated from the data with source 'fallback', preserving HTTP 200.
    """
    if not include_explanation:
        return None, "none"

    if row_count == 0 or not rows:
        logger.info("Empty query result: skipping LLM explanation call.")
        return "No rows matched this question.", "fallback"

    # Send only question, columns, top 20 rows, and total row_count
    sample_rows = rows[:20]

    try:
        explanation = provider.explain(
            question=question,
            columns=columns,
            rows=sample_rows,
            row_count=row_count,
        )
        if explanation and explanation.strip():
            return explanation.strip(), "llm"
        logger.warning("LLM provider returned empty explanation; using fallback summary.")
    except Exception as ex:
        logger.warning(
            "Explanation provider failed (%s); generating deterministic fallback.",
            type(ex).__name__,
        )

    fallback = build_fallback_summary(columns, rows, row_count)
    return fallback, "fallback"
