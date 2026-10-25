"""Integration tests for database schema, constraints, and indexes."""

import psycopg
import pytest
from psycopg import errors

from app.core.config import get_settings


@pytest.fixture(scope="module")
def owner_conn():
    """Fixture providing an active database connection as dq_owner."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_OWNER_USER,
        password=settings.POSTGRES_OWNER_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    yield conn
    conn.close()


@pytest.mark.integration
def test_all_tables_exist(owner_conn: psycopg.Connection) -> None:
    """Verify that all required tables exist in public schema."""
    expected_tables = {
        "customers",
        "products",
        "orders",
        "order_items",
        "payments",
        "alembic_version",
    }
    with owner_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public';
            """
        )
        existing_tables = {row[0] for row in cur.fetchall()}
    assert expected_tables.issubset(existing_tables), (
        f"Missing tables: {expected_tables - existing_tables}"
    )


@pytest.mark.integration
def test_app_schema_exists(owner_conn: psycopg.Connection) -> None:
    """Verify that the empty 'app' schema exists."""
    with owner_conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = 'app';
            """
        )
        assert cur.fetchone() is not None, "Schema 'app' does not exist."


@pytest.mark.integration
def test_indexes_exist(owner_conn: psycopg.Connection) -> None:
    """Verify required indexes are present on orders and order_items."""
    expected_indexes = {
        "ix_orders_customer_id",
        "ix_orders_order_date",
        "ix_order_items_order_id",
        "ix_order_items_product_id",
    }
    with owner_conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public';
            """
        )
        existing_indexes = {row[0] for row in cur.fetchall()}
    assert expected_indexes.issubset(existing_indexes), (
        f"Missing indexes: {expected_indexes - existing_indexes}"
    )


@pytest.mark.integration
def test_product_unit_price_positive_constraint(owner_conn: psycopg.Connection) -> None:
    """Verify CHECK constraint rejects non-positive product unit price."""
    with owner_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO products (id, name, category, unit_price)
                VALUES (99999, 'Invalid Zero Price Product', 'Electronics', 0.00);
                """
            )
    owner_conn.rollback()

    with owner_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO products (id, name, category, unit_price)
                VALUES (99999, 'Invalid Negative Price Product', 'Electronics', -10.00);
                """
            )
    owner_conn.rollback()


@pytest.mark.integration
def test_order_status_check_constraint(owner_conn: psycopg.Connection) -> None:
    """Verify CHECK constraint rejects invalid order statuses."""
    with owner_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO orders (id, customer_id, order_date, status)
                VALUES (99999, 1, '2024-10-01', 'processing');
                """
            )
    owner_conn.rollback()


@pytest.mark.integration
def test_order_items_quantity_positive_constraint(owner_conn: psycopg.Connection) -> None:
    """Verify CHECK constraint rejects zero or negative quantity."""
    with owner_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)
                VALUES (99999, 1, 1, 0, 99.99);
                """
            )
    owner_conn.rollback()


@pytest.mark.integration
def test_order_items_unit_price_positive_constraint(owner_conn: psycopg.Connection) -> None:
    """Verify CHECK constraint rejects zero or negative order_item unit price."""
    with owner_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)
                VALUES (99999, 1, 1, 1, 0.00);
                """
            )
    owner_conn.rollback()


@pytest.mark.integration
def test_orders_foreign_key_constraint(owner_conn: psycopg.Connection) -> None:
    """Verify foreign key constraint on orders.customer_id rejects nonexistent customer."""
    with owner_conn.cursor() as cur:
        with pytest.raises(errors.ForeignKeyViolation):
            cur.execute(
                """
                INSERT INTO orders (id, customer_id, order_date, status)
                VALUES (99999, 999999, '2024-10-01', 'placed');
                """
            )
    owner_conn.rollback()


@pytest.mark.integration
def test_customers_unique_email_constraint(owner_conn: psycopg.Connection) -> None:
    """Verify UNIQUE constraint on customers.email rejects duplicates."""
    with owner_conn.cursor() as cur:
        with pytest.raises(errors.UniqueViolation):
            cur.execute(
                """
                INSERT INTO customers (id, name, email, region, signup_date)
                VALUES (99999, 'Duplicate Customer', 'customer_0001@example.com', 'North', '2024-01-01');
                """
            )
    owner_conn.rollback()
