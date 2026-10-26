"""Unit tests for explainer service: data isolation, fallback mechanisms, and spy assertions."""

from typing import Any

from app.llm.base import LLMProvider, SQLGeneration
from app.llm.mock_provider import MockLLMProvider
from app.services.explainer import build_fallback_summary, generate_explanation


class SpyProvider(LLMProvider):
    """Spy LLMProvider to monitor calls to explain() and generate_sql()."""

    def __init__(self, return_text: str = "Mock explanation.") -> None:
        self.explain_called = False
        self.explain_call_count = 0
        self.last_explain_kwargs: dict[str, Any] = {}
        self.return_text = return_text

    def generate_sql(self, question: str, schema_context: str | None = None) -> SQLGeneration:
        return SQLGeneration(supported=True, sql="SELECT 1;")

    def explain(
        self,
        question: str,
        columns: list[str],
        rows: list[list[Any]],
        row_count: int | None = None,
        sql: str | None = None,
    ) -> str:
        self.explain_called = True
        self.explain_call_count += 1
        self.last_explain_kwargs = {
            "question": question,
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "sql": sql,
        }
        return self.return_text


def test_explainer_success_calls_provider_and_returns_llm_source():
    """Successful explanation passes sampled rows to provider and returns source 'llm'."""
    spy = SpyProvider(return_text="North America generated the highest sales.")
    cols = ["region", "revenue"]
    rows = [["North America", 150000.0], ["EMEA", 120000.0]]

    ans, source = generate_explanation(
        question="What is the revenue by region?",
        columns=cols,
        rows=rows,
        row_count=2,
        provider=spy,
    )

    assert spy.explain_called is True
    assert spy.explain_call_count == 1
    assert spy.last_explain_kwargs["question"] == "What is the revenue by region?"
    assert spy.last_explain_kwargs["columns"] == cols
    assert spy.last_explain_kwargs["rows"] == rows
    assert spy.last_explain_kwargs["row_count"] == 2
    assert ans == "North America generated the highest sales."
    assert source == "llm"


def test_explainer_empty_result_never_calls_provider_spy():
    """Empty result sets MUST NEVER call the provider (verified via Spy)."""
    spy = SpyProvider()
    cols = ["customer_id", "name"]
    rows: list[list[Any]] = []

    ans, source = generate_explanation(
        question="Which customers purchased over $1M?",
        columns=cols,
        rows=rows,
        row_count=0,
        provider=spy,
    )

    # Invariant: Spy was NEVER invoked
    assert spy.explain_called is False
    assert spy.explain_call_count == 0
    assert ans == "No rows matched this question."
    assert source == "fallback"


def test_explainer_provider_failure_returns_deterministic_fallback():
    """When the provider raises an exception, return deterministic data summary with source 'fallback'."""
    mock_fail_provider = MockLLMProvider(mode="raise_explain")
    cols = ["region", "revenue"]
    rows = [["North America", 150000.0], ["EMEA", 120000.0]]

    ans, source = generate_explanation(
        question="Top regions by revenue?",
        columns=cols,
        rows=rows,
        row_count=2,
        provider=mock_fail_provider,
    )

    assert source == "fallback"
    assert "2 rows" in ans
    assert "North America" in ans
    assert "150000.0" in ans


def test_explainer_single_value_deterministic_summary():
    """Single value queries produce clear, concise fallback summaries."""
    cols = ["total_revenue"]
    rows = [[543210.0]]
    summary = build_fallback_summary(cols, rows, 1)
    assert "total revenue" in summary
    assert "543210.0" in summary


def test_explainer_does_not_mutate_original_inputs():
    """generate_explanation must never alter columns or rows."""
    spy = SpyProvider(return_text="Valid explanation.")
    cols = ["product", "units"]
    rows = [["Widget", 10], ["Gadget", 20]]
    cols_copy = list(cols)
    rows_copy = [list(r) for r in rows]

    ans, source = generate_explanation(
        question="Units per product?",
        columns=cols,
        rows=rows,
        row_count=2,
        provider=spy,
    )

    assert cols == cols_copy
    assert rows == rows_copy


def test_explainer_samples_at_most_20_rows_for_provider():
    """When more than 20 rows are returned, at most 20 rows are passed to the provider."""
    spy = SpyProvider()
    cols = ["id", "val"]
    rows = [[i, f"val_{i}"] for i in range(50)]

    generate_explanation(
        question="List all 50 items",
        columns=cols,
        rows=rows,
        row_count=50,
        provider=spy,
    )

    assert spy.explain_called is True
    assert len(spy.last_explain_kwargs["rows"]) == 20
    assert spy.last_explain_kwargs["row_count"] == 50


def test_explainer_include_explanation_false():
    """When include_explanation is False, provider is not called and returns (None, 'none')."""
    spy = SpyProvider()
    ans, source = generate_explanation(
        question="Any question",
        columns=["col"],
        rows=[[1]],
        row_count=1,
        provider=spy,
        include_explanation=False,
    )
    assert spy.explain_called is False
    assert ans is None
    assert source == "none"
