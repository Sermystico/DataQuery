"""Security policy allowlists and schema metadata definitions.

Centralizes the single source of truth for permitted database tables, columns,
and safety boundaries. The API schema explorer strictly presents this explicit
allowlist — never introspecting raw database catalogs (pg_*, information_schema).
"""

from typing import Any

# Permitted analytical tables accessible for query generation and execution
ALLOWED_TABLES: set[str] = {
    "customers",
    "products",
    "orders",
    "order_items",
    "payments",
}

# Forbidden system catalogs and internal application tables
BANNED_TABLES: set[str] = {
    "pg_shadow",
    "pg_authid",
    "pg_database",
    "pg_user",
    "pg_roles",
    "information_schema",
    "dq_query_history",
}

# Forbidden SQL functions that could lead to DoS or credential exfiltration
BANNED_FUNCTIONS: set[str] = {
    "pg_sleep",
    "pg_read_file",
    "pg_write_file",
    "version",
    "current_user",
    "session_user",
}

# Explicit schema catalog definition for the allowed analytics tables
APPROVED_SCHEMA_METADATA: dict[str, dict[str, Any]] = {
    "customers": {
        "description": "Registered customer profiles and geographical market classifications.",
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "primary_key": True,
                "nullable": False,
                "description": "Unique customer identifier.",
                "references": None,
            },
            {
                "name": "name",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Customer display name.",
                "references": None,
            },
            {
                "name": "email",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Customer contact email address (unique).",
                "references": None,
            },
            {
                "name": "region",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Geographical market: 'North', 'South', 'East', 'West', 'Central'.",
                "references": None,
            },
            {
                "name": "signup_date",
                "type": "DATE",
                "primary_key": False,
                "nullable": False,
                "description": "Date the customer registered their account.",
                "references": None,
            },
        ],
    },
    "products": {
        "description": "Merchandise catalog containing product titles, categories, and prices.",
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "primary_key": True,
                "nullable": False,
                "description": "Unique product identifier.",
                "references": None,
            },
            {
                "name": "name",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Product title or description.",
                "references": None,
            },
            {
                "name": "category",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Merchandising category (e.g. 'Electronics', 'Apparel').",
                "references": None,
            },
            {
                "name": "unit_price",
                "type": "NUMERIC(10,2)",
                "primary_key": False,
                "nullable": False,
                "description": "Catalog unit listing price in USD (must be > 0).",
                "references": None,
            },
        ],
    },
    "orders": {
        "description": "Customer purchase transaction headers and lifecycle status.",
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "primary_key": True,
                "nullable": False,
                "description": "Unique purchase order identifier.",
                "references": None,
            },
            {
                "name": "customer_id",
                "type": "INTEGER",
                "primary_key": False,
                "nullable": False,
                "description": "Purchasing customer reference.",
                "references": "customers.id",
            },
            {
                "name": "order_date",
                "type": "DATE",
                "primary_key": False,
                "nullable": False,
                "description": "Date the purchase order was submitted.",
                "references": None,
            },
            {
                "name": "status",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Order fulfillment lifecycle state: 'placed', 'shipped', 'delivered', 'cancelled'.",
                "references": None,
            },
        ],
    },
    "order_items": {
        "description": "Individual line items for each order, capturing quantities and unit prices.",
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "primary_key": True,
                "nullable": False,
                "description": "Unique line item identifier.",
                "references": None,
            },
            {
                "name": "order_id",
                "type": "INTEGER",
                "primary_key": False,
                "nullable": False,
                "description": "Parent purchase order reference.",
                "references": "orders.id",
            },
            {
                "name": "product_id",
                "type": "INTEGER",
                "primary_key": False,
                "nullable": False,
                "description": "Purchased merchandise product reference.",
                "references": "products.id",
            },
            {
                "name": "quantity",
                "type": "INTEGER",
                "primary_key": False,
                "nullable": False,
                "description": "Number of units purchased (must be > 0).",
                "references": None,
            },
            {
                "name": "unit_price",
                "type": "NUMERIC(10,2)",
                "primary_key": False,
                "nullable": False,
                "description": "Actual price per unit billed at purchase time (must be > 0).",
                "references": None,
            },
        ],
    },
    "payments": {
        "description": "Financial billing records capturing customer payments for submitted orders.",
        "columns": [
            {
                "name": "id",
                "type": "INTEGER",
                "primary_key": True,
                "nullable": False,
                "description": "Unique payment settlement identifier.",
                "references": None,
            },
            {
                "name": "order_id",
                "type": "INTEGER",
                "primary_key": False,
                "nullable": False,
                "description": "Associated purchase order reference.",
                "references": "orders.id",
            },
            {
                "name": "amount",
                "type": "NUMERIC(12,2)",
                "primary_key": False,
                "nullable": False,
                "description": "Billed payment settlement amount in USD.",
                "references": None,
            },
            {
                "name": "method",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Payment channel: 'credit_card', 'paypal', 'bank_transfer', 'debit_card'.",
                "references": None,
            },
            {
                "name": "status",
                "type": "TEXT",
                "primary_key": False,
                "nullable": False,
                "description": "Settlement state: 'completed', 'refunded', 'failed'.",
                "references": None,
            },
            {
                "name": "paid_at",
                "type": "TIMESTAMP",
                "primary_key": False,
                "nullable": True,
                "description": "Timestamp when the payment was settled.",
                "references": None,
            },
        ],
    },
}

# Standardized business metrics and domain logic definitions
BUSINESS_DEFINITIONS: dict[str, str] = {
    "Revenue": (
        "SUM(order_items.quantity * order_items.unit_price) for orders where "
        "status != 'cancelled'. Gross billed amount on non-cancelled orders."
    ),
    "Undelivered Orders": (
        "Orders where status IN ('placed', 'shipped'). Excludes delivered orders "
        "and cancelled orders."
    ),
    "Customer Region": (
        "Geographical market classified directly from customers.region: "
        "'North', 'South', 'East', 'West', 'Central'."
    ),
    "Active Customer": (
        "A customer who has placed at least one non-cancelled order (status != 'cancelled')."
    ),
    "Average Order Value (AOV)": (
        "Total Revenue divided by count of distinct non-cancelled orders: "
        "Revenue / COUNT(DISTINCT orders.id)."
    ),
}
