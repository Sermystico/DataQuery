"""Unit tests for query schemas and chart hint models."""

import pytest
from pydantic import ValidationError

from app.schemas.query import ChartHint, QueryRequest, QueryResponse


@pytest.mark.unit
def test_chart_hint_properties_and_truthiness() -> None:
    """Verify ChartHint helper properties and boolean casting."""
    bar_hint = ChartHint(type="bar", x_key="category", y_key="revenue", title="Sales")
    assert bar_hint.chart_type == "bar"
    assert bar_hint.x_column == "category"
    assert bar_hint.y_column == "revenue"
    assert bool(bar_hint) is True

    none_hint = ChartHint(type="none")
    assert none_hint.chart_type == "none"
    assert none_hint.x_column is None
    assert none_hint.y_column is None
    assert bool(none_hint) is False


@pytest.mark.unit
def test_query_request_validation() -> None:
    """Verify QueryRequest question length boundaries and whitespace stripping."""
    # Valid
    req = QueryRequest(question="  What is total revenue?  ")
    assert req.question == "What is total revenue?"

    # Too short (< 3 non-whitespace)
    with pytest.raises(ValidationError) as exc_info:
        QueryRequest(question="  hi  ")
    assert "at least 3 non-whitespace characters" in str(exc_info.value)

    # Too long (> 500 chars) direct validator check
    with pytest.raises(ValueError, match="must not exceed 500 characters"):
        QueryRequest.validate_question("a" * 501)


@pytest.mark.unit
def test_query_response_instantiation() -> None:
    """Verify QueryResponse model serializes required analytical payload."""
    resp = QueryResponse(
        request_id="req_test_123",
        status="success",
        question="What is total revenue?",
        sql="SELECT SUM(amount) FROM payments;",
        columns=["sum"],
        rows=[[1500.0]],
        row_count=1,
        truncated=False,
        answer="The total revenue is 1500.0.",
        explanation_source="fallback",
        chart_hint=ChartHint(type="none"),
        history_id=1,
        rejection_reasons=[],
    )
    assert resp.status == "success"
    assert resp.request_id == "req_test_123"
    assert resp.row_count == 1
    assert resp.history_id == 1
    assert resp.sql == "SELECT SUM(amount) FROM payments;"
