"""Integration tests for query history recording, API pagination, security permissions, and regression."""

from unittest.mock import patch

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import errors

from app.api.v1.query import get_llm_provider
from app.core.config import get_settings
from app.llm.mock_provider import MockLLMProvider
from app.main import app


@pytest.fixture(scope="module")
def readonly_conn():
    """Connection fixture for the restricted dq_readonly role."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_READONLY_USER,
        password=settings.POSTGRES_READONLY_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    yield conn
    conn.close()


@pytest.mark.integration
def test_history_recorded_on_success(client: TestClient) -> None:
    """Successful query executions record an audit entry in app.query_history."""
    question = "What is the total revenue across all completed orders?"
    response = client.post(
        "/api/v1/query", json={"question": question, "include_explanation": True}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    history_id = data["history_id"]
    assert history_id is not None
    assert isinstance(history_id, int)
    assert data["answer"] is not None
    assert data["explanation_source"] in ("llm", "fallback")

    # Fetch recorded history item via API
    hist_resp = client.get(f"/api/v1/history/{history_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["id"] == history_id
    assert hist_data["status"] == "success"
    assert hist_data["question"] == question
    assert hist_data["sql"] is not None
    assert hist_data["row_count"] == data["row_count"]
    assert hist_data["error_code"] is None
    assert hist_data["duration_ms"] is not None


@pytest.mark.integration
def test_history_recorded_on_unsupported(client: TestClient) -> None:
    """Unsupported questions record an audit entry with error_code UNSUPPORTED_QUESTION."""
    question = "What is the price of Bitcoin in 2040?"
    response = client.post("/api/v1/query", json={"question": question})
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "unsupported"
    history_id = data["history_id"]
    assert history_id is not None

    hist_resp = client.get(f"/api/v1/history/{history_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["id"] == history_id
    assert hist_data["status"] == "unsupported"
    assert hist_data["question"] == question
    assert hist_data["sql"] is None
    assert hist_data["error_code"] == "UNSUPPORTED_QUESTION"


@pytest.mark.integration
def test_history_recorded_on_rejected(client: TestClient) -> None:
    """Rejected queries record an audit entry with error_code VALIDATION_REJECTED."""
    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="unsafe_sql")
    try:
        question = "What is the total revenue?"
        response = client.post("/api/v1/query", json={"question": question})
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "rejected"
        history_id = data["history_id"]
        assert history_id is not None

        hist_resp = client.get(f"/api/v1/history/{history_id}")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["id"] == history_id
        assert hist_data["status"] == "rejected"
        assert hist_data["error_code"] == "VALIDATION_REJECTED"
        assert hist_data["sql"] is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_history_pagination_and_sorting(client: TestClient) -> None:
    """GET /api/v1/history returns paginated results sorted newest first, with capped limit."""
    # Ensure at least 2 records exist
    client.post(
        "/api/v1/query", json={"question": "What is the total revenue across all completed orders?"}
    )
    client.post(
        "/api/v1/query", json={"question": "What is the average order value for delivered orders?"}
    )

    response = client.get("/api/v1/history?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # Verify newest first sorting (descending id)
    items = data["items"]
    assert items[0]["id"] > items[1]["id"]


@pytest.mark.integration
def test_history_pagination_bounds_enforced(client: TestClient) -> None:
    """Limit > 100 or offset < 0 return 422 validation errors."""
    resp_limit_too_high = client.get("/api/v1/history?limit=101")
    assert resp_limit_too_high.status_code == 422
    assert resp_limit_too_high.json()["error"]["code"] == "VALIDATION_ERROR"

    resp_negative_offset = client.get("/api/v1/history?offset=-1")
    assert resp_negative_offset.status_code == 422
    assert resp_negative_offset.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.integration
def test_history_detail_404_envelope(client: TestClient) -> None:
    """GET /api/v1/history/{id} for non-existent ID returns standard 404 envelope."""
    non_existent_id = 99999999
    response = client.get(f"/api/v1/history/{non_existent_id}")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert str(non_existent_id) in data["error"]["message"]
    assert "request_id" in data


@pytest.mark.integration
def test_readonly_role_cannot_read_query_history(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly role is strictly denied SELECT on app.query_history."""
    with readonly_conn.cursor() as cur:
        with pytest.raises(errors.InsufficientPrivilege):
            cur.execute("SELECT * FROM app.query_history;")
    readonly_conn.rollback()


@pytest.mark.integration
def test_history_write_failure_does_not_break_query(client: TestClient) -> None:
    """If recording history fails, the user query still succeeds with history_id=None."""
    question = "What is the total revenue across all completed orders?"

    with patch("app.services.query_service.record_query_history", return_value=None):
        response = client.post("/api/v1/query", json={"question": question})
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["history_id"] is None
        assert len(data["columns"]) > 0
        assert len(data["rows"]) > 0
        assert data["answer"] is not None


@pytest.mark.integration
def test_query_history_does_not_store_result_rows(client: TestClient) -> None:
    """Verify that app.query_history table definition has no column for raw result rows."""
    settings = get_settings()
    with psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_APP_USER,
        password=settings.POSTGRES_APP_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'app' AND table_name = 'query_history';
                """
            )
            cols = {row[0] for row in cur.fetchall()}
            assert "rows" not in cols
            assert "result_rows" not in cols
            assert "results" not in cols
            assert "data" not in cols


# --- Regression: 5 Golden Questions Check ---


@pytest.mark.integration
def test_golden_question_1_total_revenue(client: TestClient) -> None:
    """Golden 1 (AGG-01): Total revenue aggregation."""
    q = "What is the total revenue across all completed orders?"
    resp = client.post("/api/v1/query", json={"question": q})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["columns"] == ["total_revenue"]
    assert len(data["rows"]) == 1
    val = data["rows"][0][0]
    assert isinstance(val, (int, float))
    assert val > 0
    assert data["chart_hint"]["type"] == "none"
    assert data["answer"] is not None


@pytest.mark.integration
def test_golden_question_2_revenue_by_region(client: TestClient) -> None:
    """Golden 2 (GRP-01): Revenue by region (bar chart hint expected)."""
    q = "What is the total revenue broken down by customer region?"
    resp = client.post("/api/v1/query", json={"question": q})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["columns"] == ["region", "total_revenue"]
    assert len(data["rows"]) > 0
    assert len(data["rows"]) <= 20
    assert data["chart_hint"]["type"] == "bar"
    assert data["chart_hint"]["x_key"] == "region"
    assert data["chart_hint"]["y_key"] == "total_revenue"
    assert data["answer"] is not None


@pytest.mark.integration
def test_golden_question_3_monthly_orders(client: TestClient) -> None:
    """Golden 3 (DAT-04): Monthly order counts for 2024 (line chart hint expected)."""
    q = "Show monthly order counts for the year 2024."
    resp = client.post("/api/v1/query", json={"question": q})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["columns"] == ["order_month", "order_count"]
    assert len(data["rows"]) > 0
    assert data["chart_hint"]["type"] == "line"
    assert data["chart_hint"]["x_key"] == "order_month"
    assert data["chart_hint"]["y_key"] == "order_count"
    assert data["answer"] is not None


@pytest.mark.integration
def test_golden_question_4_top_products(client: TestClient) -> None:
    """Golden 4 (TOP-01): Top 5 best-selling products by quantity (bar chart expected)."""
    q = "What are the top 5 best-selling products by quantity?"
    resp = client.post("/api/v1/query", json={"question": q})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["columns"] == ["name", "total_quantity"]
    assert len(data["rows"]) <= 5
    assert data["chart_hint"]["type"] == "bar"
    assert data["chart_hint"]["x_key"] == "name"
    assert data["chart_hint"]["y_key"] == "total_quantity"
    assert data["answer"] is not None


@pytest.mark.integration
def test_golden_question_5_cancelled_orders(client: TestClient) -> None:
    """Golden 5 (FLT-03): Cancelled order count."""
    q = "How many orders are currently cancelled?"
    resp = client.post("/api/v1/query", json={"question": q})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["columns"] == ["cancelled_order_count"]
    assert len(data["rows"]) == 1
    assert data["rows"][0][0] >= 0
    assert data["chart_hint"]["type"] == "none"
    assert data["answer"] is not None
