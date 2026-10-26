"""Canonical registry of golden business questions and their reference SQL queries.

This module provides the deterministic ground-truth query mappings used by
MockLLMProvider and by evaluation suites. All SQL queries conform strictly
to PostgreSQL dialect, the 5 analytics tables, and the allowed function policy.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenQuery:
    """Canonical question with verified reference SQL and analytical category."""

    id: str
    question: str
    sql: str
    category: str


GOLDEN_QUERIES: list[GoldenQuery] = [
    # --- Aggregation ---
    GoldenQuery(
        id="AGG-01",
        question="What is the total revenue across all completed orders?",
        sql=(
            "SELECT SUM(oi.quantity * oi.unit_price) AS total_revenue "
            "FROM orders o "
            "JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status != 'cancelled';"
        ),
        category="aggregation",
    ),
    GoldenQuery(
        id="AGG-02",
        question="What is the average order value for delivered orders?",
        sql=(
            "SELECT AVG(order_total) AS average_order_value "
            "FROM ("
            "  SELECT o.id, SUM(oi.quantity * oi.unit_price) AS order_total "
            "  FROM orders o "
            "  JOIN order_items oi ON o.id = oi.order_id "
            "  WHERE o.status = 'delivered' "
            "  GROUP BY o.id"
            ") sub;"
        ),
        category="aggregation",
    ),
    GoldenQuery(
        id="AGG-03",
        question="How many total items have been purchased across all orders?",
        sql=(
            "SELECT SUM(oi.quantity) AS total_items "
            "FROM orders o "
            "JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status != 'cancelled';"
        ),
        category="aggregation",
    ),
    GoldenQuery(
        id="AGG-04",
        question="What is the minimum and maximum product price in our catalog?",
        sql="SELECT MIN(unit_price) AS min_price, MAX(unit_price) AS max_price FROM products;",
        category="aggregation",
    ),
    GoldenQuery(
        id="AGG-05",
        question="How many unique customers have placed at least one order?",
        sql="SELECT COUNT(DISTINCT customer_id) AS active_customer_count FROM orders WHERE status != 'cancelled';",
        category="aggregation",
    ),
    # --- Grouping & Summaries ---
    GoldenQuery(
        id="GRP-01",
        question="What is the total revenue broken down by customer region?",
        sql=(
            "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS total_revenue "
            "FROM customers c "
            "JOIN orders o ON c.id = o.customer_id "
            "JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status != 'cancelled' "
            "GROUP BY c.region "
            "ORDER BY total_revenue DESC, c.region ASC;"
        ),
        category="grouping",
    ),
    GoldenQuery(
        id="GRP-02",
        question="Count the total number of orders by fulfillment status.",
        sql="SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status ORDER BY order_count DESC, status ASC;",
        category="grouping",
    ),
    GoldenQuery(
        id="GRP-03",
        question="What is the average product unit price in each category?",
        sql="SELECT category, ROUND(AVG(unit_price), 2) AS avg_unit_price FROM products GROUP BY category ORDER BY avg_unit_price DESC, category ASC;",
        category="grouping",
    ),
    GoldenQuery(
        id="GRP-04",
        question="List product categories that have generated more than $10,000 in revenue.",
        sql=(
            "SELECT p.category, SUM(oi.quantity * oi.unit_price) AS total_revenue "
            "FROM products p "
            "JOIN order_items oi ON p.id = oi.product_id "
            "JOIN orders o ON oi.order_id = o.id "
            "WHERE o.status != 'cancelled' "
            "GROUP BY p.category "
            "HAVING SUM(oi.quantity * oi.unit_price) > 10000 "
            "ORDER BY total_revenue DESC, p.category ASC;"
        ),
        category="grouping",
    ),
    GoldenQuery(
        id="GRP-05",
        question="How many customers registered in each geographical region?",
        sql="SELECT region, COUNT(*) AS customer_count FROM customers GROUP BY region ORDER BY customer_count DESC, region ASC;",
        category="grouping",
    ),
    # --- Top-N & Ranking ---
    GoldenQuery(
        id="TOP-01",
        question="What are the top 5 best-selling products by quantity?",
        sql=(
            "SELECT p.name, SUM(oi.quantity) AS total_quantity "
            "FROM products p "
            "JOIN order_items oi ON p.id = oi.product_id "
            "JOIN orders o ON oi.order_id = o.id "
            "WHERE o.status != 'cancelled' "
            "GROUP BY p.name "
            "ORDER BY total_quantity DESC, p.name ASC "
            "LIMIT 5;"
        ),
        category="ranking",
    ),
    GoldenQuery(
        id="TOP-02",
        question="Who are the top 3 customers by total spend?",
        sql=(
            "SELECT c.name, SUM(oi.quantity * oi.unit_price) AS total_spend "
            "FROM customers c "
            "JOIN orders o ON c.id = o.customer_id "
            "JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status != 'cancelled' "
            "GROUP BY c.name "
            "ORDER BY total_spend DESC, c.name ASC "
            "LIMIT 3;"
        ),
        category="ranking",
    ),
    GoldenQuery(
        id="TOP-03",
        question="What is the single most expensive product in inventory?",
        sql="SELECT name, unit_price FROM products ORDER BY unit_price DESC, name ASC LIMIT 1;",
        category="ranking",
    ),
    GoldenQuery(
        id="TOP-04",
        question="What are the top 3 product categories by revenue?",
        sql=(
            "SELECT p.category, SUM(oi.quantity * oi.unit_price) AS total_revenue "
            "FROM products p "
            "JOIN order_items oi ON p.id = oi.product_id "
            "JOIN orders o ON oi.order_id = o.id "
            "WHERE o.status != 'cancelled' "
            "GROUP BY p.category "
            "ORDER BY total_revenue DESC, p.category ASC "
            "LIMIT 3;"
        ),
        category="ranking",
    ),
    GoldenQuery(
        id="TOP-05",
        question="Find the 5 most recent orders placed in the system.",
        sql="SELECT id, customer_id, order_date, status FROM orders ORDER BY order_date DESC, id DESC LIMIT 5;",
        category="ranking",
    ),
    # --- Date-Based Queries (Anchored to 2024-11-01) ---
    GoldenQuery(
        id="DAT-01",
        question="What was the total revenue generated in October 2024?",
        sql=(
            "SELECT SUM(oi.quantity * oi.unit_price) AS total_revenue "
            "FROM orders o "
            "JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status != 'cancelled' "
            "AND o.order_date >= '2024-10-01' "
            "AND o.order_date < '2024-11-01';"
        ),
        category="date_based",
    ),
    GoldenQuery(
        id="DAT-02",
        question="How many orders were placed in the last 30 days?",
        sql="SELECT COUNT(*) AS order_count FROM orders WHERE order_date >= '2024-10-02' AND order_date <= '2024-11-01';",
        category="date_based",
    ),
    GoldenQuery(
        id="DAT-03",
        question="How many customers signed up between June 1, 2024 and August 31, 2024?",
        sql="SELECT COUNT(*) AS customer_count FROM customers WHERE signup_date >= '2024-06-01' AND signup_date <= '2024-08-31';",
        category="date_based",
    ),
    GoldenQuery(
        id="DAT-04",
        question="Show monthly order counts for the year 2024.",
        sql=(
            "SELECT DATE_TRUNC('month', order_date) AS order_month, COUNT(*) AS order_count "
            "FROM orders "
            "WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01' "
            "GROUP BY DATE_TRUNC('month', order_date) "
            "ORDER BY order_month ASC;"
        ),
        category="date_based",
    ),
    GoldenQuery(
        id="DAT-05",
        question="Compare revenue in October 2024 versus September 2024.",
        sql=(
            "SELECT DATE_TRUNC('month', o.order_date) AS order_month, SUM(oi.quantity * oi.unit_price) AS monthly_revenue "
            "FROM orders o "
            "JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.status != 'cancelled' "
            "AND o.order_date >= '2024-09-01' "
            "AND o.order_date < '2024-11-01' "
            "GROUP BY DATE_TRUNC('month', o.order_date) "
            "ORDER BY order_month ASC;"
        ),
        category="date_based",
    ),
    # --- Undelivered Orders ---
    GoldenQuery(
        id="FUL-01",
        question="How many orders are currently placed or shipped but not yet delivered?",
        sql="SELECT COUNT(*) AS undelivered_count FROM orders WHERE status IN ('placed', 'shipped');",
        category="fulfillment",
    ),
    # --- Filtering ---
    GoldenQuery(
        id="FLT-01",
        question="List all customers located in the EMEA region.",
        sql="SELECT id, name, email FROM customers WHERE region = 'EMEA' ORDER BY id ASC;",
        category="filtering",
    ),
    GoldenQuery(
        id="FLT-02",
        question="Show all products priced over $100.",
        sql="SELECT id, name, category, unit_price FROM products WHERE unit_price > 100 ORDER BY unit_price DESC, id ASC;",
        category="filtering",
    ),
    GoldenQuery(
        id="FLT-03",
        question="How many orders are currently cancelled?",
        sql="SELECT COUNT(*) AS cancelled_order_count FROM orders WHERE status = 'cancelled';",
        category="filtering",
    ),
    # --- Table Joins ---
    GoldenQuery(
        id="JOIN-01",
        question="Show order ID, customer name, and order date for the 50 most recent placed orders.",
        sql=(
            "SELECT o.id, c.name, o.order_date "
            "FROM orders o "
            "JOIN customers c ON o.customer_id = c.id "
            "WHERE o.status = 'placed' "
            "ORDER BY o.order_date DESC, o.id DESC "
            "LIMIT 50;"
        ),
        category="joins",
    ),
    GoldenQuery(
        id="JOIN-02",
        question="List each product name alongside its total units sold.",
        sql=(
            "SELECT p.name, COALESCE(SUM(CASE WHEN o.id IS NOT NULL THEN oi.quantity ELSE 0 END), 0) AS total_units_sold "
            "FROM products p "
            "LEFT JOIN order_items oi ON p.id = oi.product_id "
            "LEFT JOIN orders o ON oi.order_id = o.id AND o.status != 'cancelled' "
            "GROUP BY p.name "
            "ORDER BY total_units_sold DESC, p.name ASC;"
        ),
        category="joins",
    ),
    GoldenQuery(
        id="JOIN-03",
        question="Which customers have never placed any orders?",
        sql="SELECT c.id, c.name, c.email FROM customers c LEFT JOIN orders o ON c.id = o.customer_id WHERE o.id IS NULL ORDER BY c.id ASC;",
        category="joins",
    ),
    GoldenQuery(
        id="PAY-01",
        question="Show payment methods breakdown by total collected amount.",
        sql=(
            "SELECT method, SUM(amount) AS total_amount, COUNT(*) AS transaction_count "
            "FROM payments "
            "WHERE status = 'completed' "
            "GROUP BY method "
            "ORDER BY total_amount DESC, method ASC;"
        ),
        category="payments",
    ),
    GoldenQuery(
        id="AGG-06",
        question="What is the total amount of all successful payments?",
        sql="SELECT SUM(amount) AS total_successful_payments FROM payments WHERE status = 'completed';",
        category="aggregation",
    ),
    GoldenQuery(
        id="GRP-06",
        question="What is the total revenue and order count for each payment method?",
        sql=(
            "SELECT method, SUM(amount) AS total_amount, COUNT(*) AS payment_count "
            "FROM payments "
            "GROUP BY method "
            "ORDER BY total_amount DESC, method ASC;"
        ),
        category="grouping",
    ),
    GoldenQuery(
        id="FLT-04",
        question="List all orders placed on November 1, 2024.",
        sql="SELECT id, customer_id, status FROM orders WHERE order_date = '2024-11-01' ORDER BY id ASC;",
        category="filtering",
    ),
    GoldenQuery(
        id="PAY-02",
        question="How many payments failed or were refunded?",
        sql="SELECT status, COUNT(*) AS payment_count FROM payments WHERE status IN ('failed', 'refunded') GROUP BY status ORDER BY payment_count DESC, status ASC;",
        category="payments",
    ),
]

