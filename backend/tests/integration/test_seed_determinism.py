"""Integration tests for seed dataset determinism, idempotency, and ranking integrity."""

from datetime import date

import psycopg
import pytest

from app.core.config import get_settings
from seed.dataset import generate_dataset
from seed.load import load_seed_data


@pytest.fixture(scope="module")
def owner_conn():
    """Connection fixture as dq_owner role."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_OWNER_USER,
        password=settings.POSTGRES_OWNER_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    yield conn
    conn.close()


@pytest.mark.integration
def test_generate_dataset_pure_determinism() -> None:
    """Verify generate_dataset returns bit-for-bit identical dicts when called with same seed."""
    d1 = generate_dataset(seed=42, as_of=date(2024, 11, 1))
    d2 = generate_dataset(seed=42, as_of=date(2024, 11, 1))
    assert d1 == d2, "generate_dataset is not deterministic!"


@pytest.mark.integration
def test_seed_row_counts_in_database(owner_conn: psycopg.Connection) -> None:
    """Verify that expected row counts exist in the database."""
    expected_counts = {
        "customers": 200,
        "products": 37,
        "orders": 1500,
        "order_items": 3866,
        "payments": 1500,
    }

    with owner_conn.cursor() as cur:
        for table, expected in expected_counts.items():
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            actual = cur.fetchone()[0]
            assert actual == expected, f"Table '{table}' expected {expected} rows, found {actual}"


@pytest.mark.integration
def test_seed_loading_idempotence() -> None:
    """Verify loading twice via load_seed_data(force=True) gives identical row counts."""
    counts1 = load_seed_data(force=True)
    counts2 = load_seed_data(force=True)
    assert counts1 == counts2, f"Idempotent load produced differing counts: {counts1} vs {counts2}"


@pytest.mark.integration
def test_no_top_n_ties_in_dataset(owner_conn: psycopg.Connection) -> None:
    """Verify that top-N business analytics queries have unambiguous rank ordering with zero ties."""
    with owner_conn.cursor() as cur:
        # 1. Top 5 products by revenue (excluding cancelled orders)
        cur.execute(
            """
            SELECT p.id, SUM(oi.quantity * oi.unit_price) AS revenue
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status != 'cancelled'
            GROUP BY p.id
            ORDER BY revenue DESC
            LIMIT 6;
            """
        )
        top_products = cur.fetchall()
        assert len(top_products) == 6, "Expected at least 6 products"
        top5_revenues = [row[1] for row in top_products[:5]]
        assert len(set(top5_revenues)) == 5, (
            f"Ties detected in top 5 products by revenue: {top5_revenues}"
        )
        for i in range(len(top5_revenues) - 1):
            assert top5_revenues[i] > top5_revenues[i + 1], (
                f"Rank {i + 1} does not strictly exceed rank {i + 2}"
            )

        # 2. Top customer by spend
        cur.execute(
            """
            SELECT c.id, SUM(oi.quantity * oi.unit_price) AS total_spend
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status != 'cancelled'
            GROUP BY c.id
            ORDER BY total_spend DESC
            LIMIT 2;
            """
        )
        top_customers = cur.fetchall()
        assert len(top_customers) == 2, "Expected at least 2 customers"
        assert top_customers[0][1] > top_customers[1][1], (
            f"Tie detected for #1 customer spend: {top_customers[0]} vs {top_customers[1]}"
        )

        # 3. Top region by order count
        cur.execute(
            """
            SELECT c.region, COUNT(o.id) AS order_count
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            GROUP BY c.region
            ORDER BY order_count DESC
            LIMIT 2;
            """
        )
        top_regions = cur.fetchall()
        assert len(top_regions) == 2, "Expected at least 2 regions"
        assert top_regions[0][1] > top_regions[1][1], (
            f"Tie detected for #1 region order count: {top_regions[0]} vs {top_regions[1]}"
        )
