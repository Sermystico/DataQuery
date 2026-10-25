"""Integration tests for GET /api/v1/schema endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.security.policy import ALLOWED_TABLES, BANNED_TABLES


@pytest.mark.integration
def test_schema_returns_only_approved_tables(client: TestClient) -> None:
    """Verify /schema returns exactly the approved tables and no system catalogs."""
    response = client.get("/api/v1/schema")
    assert response.status_code == 200
    data = response.json()

    assert "database" in data
    assert "as_of_date" in data
    assert "tables" in data
    assert "business_definitions" in data

    table_names = {t["name"] for t in data["tables"]}

    # Must match ALLOWED_TABLES exactly
    assert table_names == ALLOWED_TABLES
    assert table_names == {"customers", "products", "orders", "order_items", "payments"}

    # Must NOT contain any banned tables or system catalogs
    for banned in BANNED_TABLES:
        assert banned not in table_names

    for name in table_names:
        assert not name.startswith("pg_")
        assert not name.startswith("information_schema")
        assert not name.startswith("app")
        assert not name.startswith("dq_")


@pytest.mark.integration
def test_schema_table_and_column_metadata(client: TestClient) -> None:
    """Verify detailed column attributes and descriptions are present for all tables."""
    response = client.get("/api/v1/schema")
    assert response.status_code == 200
    data = response.json()

    for table in data["tables"]:
        assert table["name"] in ALLOWED_TABLES
        assert len(table["description"]) > 0
        assert len(table["columns"]) > 0

        # Check column properties
        for col in table["columns"]:
            assert "name" in col
            assert "type" in col
            assert "primary_key" in col
            assert "nullable" in col
            assert "description" in col
            assert len(col["description"]) > 0


@pytest.mark.integration
def test_schema_business_definitions(client: TestClient) -> None:
    """Verify required business metrics are present in the definitions catalog."""
    response = client.get("/api/v1/schema")
    assert response.status_code == 200
    data = response.json()

    defs = data["business_definitions"]
    assert "Revenue" in defs
    assert "Undelivered Orders" in defs
    assert "Customer Region" in defs
    assert "Active Customer" in defs
    assert "Average Order Value (AOV)" in defs
