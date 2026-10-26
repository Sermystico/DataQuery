"""Tests verifying PostgreSQL kernel permissions alone block all malicious actions.

This test file explicitly BYPASSES the application-level SQL validator and
sends dangerous SQL payloads directly over a raw dq_readonly database connection.
This demonstrates the defense-in-depth model: even if an attacker were to
completely compromise or circumvent the AST validator, PostgreSQL permissions
alone strictly block writes, DDL, administrative commands, catalog access,
and access to the application schema, leaving all seed table row counts unmodified.
"""

import psycopg
import pytest
from psycopg import errors

from app.core.config import get_settings

ANALYTICS_TABLES = ["customers", "products", "orders", "order_items", "payments"]


@pytest.fixture(scope="module")
def readonly_raw_conn():
    """Direct psycopg connection authenticating as dq_readonly."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_READONLY_USER,
        password=settings.POSTGRES_READONLY_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        autocommit=False,
    )
    yield conn
    conn.close()


def _get_table_counts(conn: psycopg.Connection) -> dict[str, int]:
    """Retrieve current row counts for all 5 analytics tables."""
    counts = {}
    with conn.cursor() as cur:
        for tbl in ANALYTICS_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            counts[tbl] = cur.fetchone()[0]
    return counts


@pytest.mark.security
@pytest.mark.integration
def test_db_permissions_alone_block_all_dangerous_operations(
    readonly_raw_conn: psycopg.Connection,
) -> None:
    """Verify raw malicious statements fail at the PostgreSQL layer and row counts remain invariant."""
    initial_counts = _get_table_counts(readonly_raw_conn)
    assert all(c > 0 for c in initial_counts.values()), "Analytics tables must be seeded."

    dangerous_payloads = [
        # DML
        (
            "INSERT INTO customers (name, email, region, signup_date) VALUES ('Evil', 'e@x.com', 'North', '2024-01-01');",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        (
            "UPDATE customers SET name = 'Owned' WHERE id = 1;",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        (
            "DELETE FROM orders WHERE id = 1;",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        # DDL
        (
            "DROP TABLE customers CASCADE;",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        (
            "ALTER TABLE products ADD COLUMN backdoor TEXT;",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        (
            "CREATE TABLE hacked_tbl (id INT);",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        (
            "TRUNCATE TABLE order_items;",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        # Administrative & Permissions
        (
            "GRANT ALL PRIVILEGES ON customers TO public;",
            (errors.InsufficientPrivilege, errors.ReadOnlySqlTransaction),
        ),
        # Protected schemas and tables
        ("SELECT * FROM app.dq_query_history;", (errors.InsufficientPrivilege,)),
        ("SELECT * FROM pg_authid;", (errors.InsufficientPrivilege,)),
        ("SELECT * FROM pg_shadow;", (errors.InsufficientPrivilege,)),
    ]

    for sql, expected_errors in dangerous_payloads:
        try:
            with readonly_raw_conn.cursor() as cur:
                with pytest.raises(expected_errors):
                    cur.execute(sql)
        finally:
            readonly_raw_conn.rollback()

    # Verify table row counts are 100% untouched
    after_counts = _get_table_counts(readonly_raw_conn)
    assert initial_counts == after_counts, (
        f"Database state was modified! Before: {initial_counts}, After: {after_counts}"
    )
