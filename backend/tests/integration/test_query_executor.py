"""Integration tests for query_executor and POST /api/v1/sql/validate."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import QueryTimeout
from app.security.query_executor import execute_query
from app.security.sql_validator import validate_sql


@pytest.mark.integration
def test_executor_rejects_raw_strings_and_unvalidated_input() -> None:
    """Verify execute_query rejects raw strings or foreign objects with TypeError."""
    with pytest.raises(TypeError, match="accepts only ValidatedSQL instances"):
        execute_query("SELECT 1")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="accepts only ValidatedSQL instances"):
        execute_query({"sql": "SELECT 1"})  # type: ignore[arg-type]


@pytest.mark.integration
def test_executor_runs_valid_seed_queries() -> None:
    """Verify executor executes valid queries against seed data and returns correct rows."""
    validation = validate_sql("SELECT count(*) AS total_customers FROM customers;")
    assert validation.valid is True
    assert validation.validated_sql is not None

    result = execute_query(validation.validated_sql)
    assert result.columns == ["total_customers"]
    assert len(result.rows) == 1
    assert result.rows[0][0] > 0
    assert result.truncated is False
    assert result.duration_ms >= 0


@pytest.mark.integration
def test_executor_group_by_join_query() -> None:
    """Verify executor correctly processes aggregations with JOINs."""
    query = """
    SELECT c.region, count(o.id) AS order_count
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    GROUP BY c.region
    ORDER BY order_count DESC;
    """
    validation = validate_sql(query)
    assert validation.valid is True
    assert validation.validated_sql is not None

    result = execute_query(validation.validated_sql)
    assert "region" in result.columns
    assert "order_count" in result.columns
    assert len(result.rows) > 0


@pytest.mark.integration
def test_executor_truncation_flag_and_limit() -> None:
    """Verify executor truncates rows and sets truncated=True when row count exceeds max_rows."""
    # Seed data has at least 50 orders
    validation = validate_sql("SELECT id, status FROM orders;", max_rows=5)
    assert validation.valid is True
    assert validation.validated_sql is not None

    result = execute_query(validation.validated_sql, max_rows=5)
    assert len(result.rows) == 5
    assert result.truncated is True
    assert result.columns == ["id", "status"]


@pytest.mark.integration
def test_executor_statement_timeout_cancels_heavy_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify statement_timeout cancels heavy legal queries and raises QueryTimeout.

    Uses a legal cross join of order_items with itself multiple times.
    """
    settings = get_settings()
    # Temporarily set timeout to 100ms to guarantee cancellation
    monkeypatch.setattr(settings, "QUERY_TIMEOUT_MS", 100)

    # Cross join of 500+ order_items creates ~62 billion rows, guaranteed to exceed 100ms
    heavy_sql = """
    SELECT count(*)
    FROM order_items oi1
    CROSS JOIN order_items oi2
    CROSS JOIN order_items oi3
    CROSS JOIN order_items oi4;
    """
    validation = validate_sql(heavy_sql)
    assert validation.valid is True
    assert validation.validated_sql is not None

    with pytest.raises(QueryTimeout):
        execute_query(validation.validated_sql)


@pytest.mark.integration
def test_api_sql_validate_endpoint_valid_query(client: TestClient) -> None:
    """Verify POST /api/v1/sql/validate returns 200 with valid=True for benign SQL."""
    response = client.post(
        "/api/v1/sql/validate",
        json={"sql": "SELECT id, name FROM customers WHERE region = 'North';"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["reasons"] == []
    assert "SELECT" in data["normalized_sql"]
    assert "LIMIT" in data["normalized_sql"]


@pytest.mark.integration
def test_api_sql_validate_endpoint_malicious_query(client: TestClient) -> None:
    """Verify POST /api/v1/sql/validate returns 200 with valid=False for rejected SQL."""
    response = client.post(
        "/api/v1/sql/validate",
        json={"sql": "DROP TABLE customers;"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert len(data["reasons"]) > 0
    assert data["normalized_sql"] is None
