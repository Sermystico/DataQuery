"""Unit tests for the SQL syntax and policy validator."""

from unittest.mock import patch

import pytest

from app.security.sql_validator import ValidatedSQL, validate_sql

VALID_QUERIES = [
    # 1. Simple select
    "SELECT id, name FROM customers",
    # 2. Select with WHERE
    "SELECT id, name, region FROM customers WHERE region = 'North'",
    # 3. Aggregate SUM and AVG
    "SELECT SUM(quantity), AVG(unit_price) FROM order_items",
    # 4. Aggregate COUNT, MIN, MAX
    "SELECT COUNT(*), MIN(unit_price), MAX(unit_price) FROM products",
    # 5. GROUP BY and HAVING
    "SELECT category, AVG(unit_price) FROM products GROUP BY category HAVING COUNT(*) > 1",
    # 6. Two-table JOIN
    "SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id",
    # 7. Three-table JOIN
    "SELECT c.name, o.id, oi.quantity FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id",
    # 8. Four-table JOIN
    "SELECT c.name, p.name, oi.quantity FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id JOIN products p ON oi.product_id = p.id",
    # 9. Five-table JOIN
    "SELECT c.name, pay.amount FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id JOIN products p ON oi.product_id = p.id JOIN payments pay ON o.id = pay.order_id",
    # 10. CTE (Common Table Expression)
    "WITH regional_rev AS (SELECT c.region, SUM(oi.quantity * oi.unit_price) AS rev FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id WHERE o.status != 'cancelled' GROUP BY c.region) SELECT region, rev FROM regional_rev ORDER BY rev DESC",
    # 11. Multiple CTEs
    "WITH cust AS (SELECT id, name FROM customers WHERE region = 'North'), ord AS (SELECT id, customer_id FROM orders WHERE status = 'delivered') SELECT cust.name, ord.id FROM cust JOIN ord ON cust.id = ord.customer_id",
    # 12. Window function ROW_NUMBER
    "SELECT id, category, unit_price, ROW_NUMBER() OVER (PARTITION BY category ORDER BY unit_price DESC) AS rnk FROM products",
    # 13. Window function RANK & DENSE_RANK
    "SELECT id, category, unit_price, RANK() OVER (PARTITION BY category ORDER BY unit_price DESC) AS rnk, DENSE_RANK() OVER (PARTITION BY category ORDER BY unit_price DESC) AS drnk FROM products",
    # 14. Window function LAG & LEAD
    "SELECT id, order_date, LAG(order_date) OVER (ORDER BY order_date) AS prev_date, LEAD(order_date) OVER (ORDER BY order_date) AS next_date FROM orders",
    # 15. DATE_TRUNC function
    "SELECT DATE_TRUNC('month', order_date) AS order_month, COUNT(*) AS order_cnt FROM orders GROUP BY DATE_TRUNC('month', order_date)",
    # 16. EXTRACT function
    "SELECT EXTRACT(year FROM order_date) AS order_year, COUNT(*) FROM orders GROUP BY EXTRACT(year FROM order_date)",
    # 17. Subquery in WHERE
    "SELECT name, unit_price FROM products WHERE unit_price > (SELECT AVG(unit_price) FROM products)",
    # 18. Subquery with IN
    "SELECT name FROM customers WHERE id IN (SELECT customer_id FROM orders WHERE status = 'delivered')",
    # 19. Subquery with EXISTS
    "SELECT name FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)",
    # 20. CASE expression
    "SELECT id, status, CASE WHEN status = 'delivered' THEN 'Complete' WHEN status = 'cancelled' THEN 'Void' ELSE 'Pending' END AS lifecycle FROM orders",
    # 21. COALESCE and NULLIF
    "SELECT id, COALESCE(NULLIF(status, 'cancelled'), 'other') FROM orders",
    # 22. String functions LOWER and UPPER
    "SELECT LOWER(name), UPPER(region) FROM customers",
    # 23. Mathematical ABS and ROUND
    "SELECT id, ROUND(unit_price, 0), ABS(unit_price) FROM products",
    # 24. CAST expression
    "SELECT id, CAST(order_date AS TEXT) FROM orders",
    # 25. Explicit public schema qualification
    "SELECT id, name FROM public.customers",
    # 26. UNION of selects
    "SELECT name AS label FROM customers UNION SELECT name AS label FROM products",
    # 27. Query with pre-existing small LIMIT
    "SELECT id FROM orders LIMIT 10",
    # 28. Query with large LIMIT that gets clamped
    "SELECT id FROM orders LIMIT 500",
]


@pytest.mark.unit
def test_at_least_25_valid_queries_defined() -> None:
    """Verify test catalog contains at least 25 distinct analytical queries."""
    assert len(VALID_QUERIES) >= 25


@pytest.mark.unit
@pytest.mark.parametrize("query", VALID_QUERIES)
def test_valid_queries_accepted_and_normalized(query: str) -> None:
    """Verify every valid analytical query is accepted, policy-compliant, and contains a LIMIT."""
    result = validate_sql(query, max_rows=100)
    assert result.valid is True, f"Expected valid for query: {query}. Reasons: {result.reasons}"
    assert result.reasons == []
    assert result.normalized_sql is not None
    assert "LIMIT" in result.normalized_sql.upper()
    assert isinstance(result.validated_sql, ValidatedSQL)
    assert result.validated_sql.sql == result.normalized_sql


@pytest.mark.unit
def test_limit_clamping_logic() -> None:
    """Verify LIMIT clamp/injection behavior for varying max_rows."""
    # 1. No limit -> inject max_rows + 1
    res1 = validate_sql("SELECT name FROM products", max_rows=50)
    assert res1.valid is True
    assert "LIMIT 51" in res1.normalized_sql

    # 2. Existing limit 5 <= 51 -> preserved as 5
    res2 = validate_sql("SELECT name FROM products LIMIT 5", max_rows=50)
    assert res2.valid is True
    assert "LIMIT 5" in res2.normalized_sql

    # 3. Existing limit 200 > 51 -> clamped to 51
    res3 = validate_sql("SELECT name FROM products LIMIT 200", max_rows=50)
    assert res3.valid is True
    assert "LIMIT 51" in res3.normalized_sql


@pytest.mark.unit
def test_comments_stripped_from_normalized_sql() -> None:
    """Verify inline and block comments are completely stripped in normalized SQL."""
    query = "SELECT /* block comment */ name -- line comment\nFROM products"
    result = validate_sql(query)
    assert result.valid is True
    assert "/*" not in result.normalized_sql
    assert "--" not in result.normalized_sql
    assert "comment" not in result.normalized_sql


@pytest.mark.unit
def test_validated_sql_token_security() -> None:
    """Verify ValidatedSQL cannot be instantiated directly by external code."""
    with pytest.raises(PermissionError) as exc_info:
        ValidatedSQL("DROP TABLE orders", _token=object())
    assert "cannot be instantiated directly" in str(exc_info.value)


@pytest.mark.unit
def test_validated_sql_str_and_repr() -> None:
    """Verify ValidatedSQL __str__ and __repr__ return expected strings."""
    res = validate_sql("SELECT id FROM orders LIMIT 5")
    assert res.validated_sql is not None
    assert str(res.validated_sql) == res.normalized_sql
    assert repr(res.validated_sql) == f"ValidatedSQL({res.normalized_sql!r})"


@pytest.mark.unit
def test_validate_sql_type_and_length_boundaries() -> None:
    """Verify non-string, empty, and excessive length queries are rejected safely."""
    # Non-string input
    res_non_str = validate_sql(12345)  # type: ignore
    assert res_non_str.valid is False
    assert "Query must be a string." in res_non_str.reasons

    # Empty string
    res_empty = validate_sql("   \n\t  ")
    assert res_empty.valid is False
    assert "Query is empty or whitespace-only." in res_empty.reasons

    # > 5000 chars
    res_long = validate_sql("SELECT " + "a" * 5001)
    assert res_long.valid is False
    assert "exceeds 5000 character maximum limit" in res_long.reasons[0]


@pytest.mark.unit
def test_validate_sql_empty_semicolons() -> None:
    """Verify standalone semicolons return no valid statements error."""
    res = validate_sql(";;; ; ")
    assert res.valid is False
    assert "No valid SQL statements found." in res.reasons


@pytest.mark.unit
def test_validate_sql_unknown_column_on_table() -> None:
    """Verify column resolution error and post-qualify defense-in-depth column checks."""
    # Line 317: Natural column resolution error raised by qualify()
    res = validate_sql("SELECT customers.nonexistent_secret_column FROM customers")
    assert res.valid is False
    assert any("Column resolution error" in r for r in res.reasons)

    # Lines 326, 329: Defense-in-depth check if qualify passes an invalid column
    import sqlglot.expressions as exp
    mock_ast = validate_sql("SELECT id FROM customers").validated_sql  # valid base
    assert mock_ast is not None

    fake_col = exp.Column(this=exp.to_identifier("bad_col"), table=exp.to_identifier("customers"))
    fake_query = exp.select(fake_col).from_("customers")

    with patch("app.security.sql_validator.qualify", return_value=fake_query):
        res_mocked = validate_sql("SELECT id FROM customers")
        assert res_mocked.valid is False
        assert any("Unknown column 'bad_col' on table 'customers'" in r for r in res_mocked.reasons)


@pytest.mark.unit
def test_validate_sql_non_integer_limit_clamped() -> None:
    """Verify non-integer or unusual LIMIT clauses are safely normalized and clamped."""
    res = validate_sql("SELECT id FROM orders LIMIT ALL")
    assert res.valid is True
    assert "LIMIT 101" in res.normalized_sql
