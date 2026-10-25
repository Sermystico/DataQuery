"""Integration tests for database role permissions and security isolation."""

import psycopg
import pytest
from psycopg import errors

from app.core.config import get_settings


@pytest.fixture(scope="module")
def readonly_conn():
    """Connection fixture as dq_readonly role."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_READONLY_USER,
        password=settings.POSTGRES_READONLY_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def app_conn():
    """Connection fixture as dq_app role."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_APP_USER,
        password=settings.POSTGRES_APP_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    yield conn
    conn.close()


@pytest.mark.integration
def test_readonly_select_allowed_on_analytics_tables(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly can execute SELECT on all 5 analytics tables."""
    tables = ["customers", "products", "orders", "order_items", "payments"]
    with readonly_conn.cursor() as cur:
        for tbl in tables:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            count = cur.fetchone()[0]
            assert count >= 0, f"Failed reading count from {tbl}"


@pytest.mark.integration
def test_readonly_insert_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly cannot INSERT rows into analytics tables."""
    with readonly_conn.cursor() as cur:
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            cur.execute(
                """
                INSERT INTO customers (name, email, region, signup_date)
                VALUES ('Hacker Customer', 'hacker@example.com', 'North', '2024-01-01');
                """
            )
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_update_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly cannot UPDATE rows in analytics tables."""
    with readonly_conn.cursor() as cur:
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            cur.execute("UPDATE products SET unit_price = 1.00 WHERE id = 1;")
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_delete_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly cannot DELETE rows from analytics tables."""
    with readonly_conn.cursor() as cur:
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            cur.execute("DELETE FROM customers WHERE id = 1;")
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_drop_table_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly cannot DROP analytics tables."""
    with readonly_conn.cursor() as cur:
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            cur.execute("DROP TABLE customers;")
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_create_table_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly cannot CREATE tables in public schema."""
    with readonly_conn.cursor() as cur:
        with pytest.raises((errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction)):
            cur.execute("CREATE TABLE public.unauthorized_test (id INT);")
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_catalog_access_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly is denied access to sensitive system authentication catalogs."""
    with readonly_conn.cursor() as cur:
        with pytest.raises(errors.InsufficientPrivilege):
            cur.execute("SELECT * FROM pg_shadow;")
    readonly_conn.rollback()

    with readonly_conn.cursor() as cur:
        with pytest.raises(errors.InsufficientPrivilege):
            cur.execute("SELECT * FROM pg_authid;")
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_app_schema_access_fails(readonly_conn: psycopg.Connection) -> None:
    """Verify dq_readonly cannot access or inspect objects in the 'app' schema."""
    with readonly_conn.cursor() as cur:
        with pytest.raises(errors.InsufficientPrivilege):
            cur.execute("SELECT * FROM app.query_history;")
    readonly_conn.rollback()


@pytest.mark.integration
def test_readonly_statement_timeout_applied(readonly_conn: psycopg.Connection) -> None:
    """Verify that statement_timeout cancels queries exceeding the configured threshold."""
    settings = get_settings()
    sleep_seconds = (settings.QUERY_TIMEOUT_MS / 1000.0) + 1.5

    with readonly_conn.cursor() as cur:
        with pytest.raises(errors.QueryCanceled):
            cur.execute(f"SELECT pg_sleep({sleep_seconds});")
    readonly_conn.rollback()


@pytest.mark.integration
def test_app_role_cannot_read_analytics_tables(app_conn: psycopg.Connection) -> None:
    """Verify dq_app has zero access to public analytics tables."""
    with app_conn.cursor() as cur:
        with pytest.raises(errors.InsufficientPrivilege):
            cur.execute("SELECT COUNT(*) FROM public.customers;")
    app_conn.rollback()
