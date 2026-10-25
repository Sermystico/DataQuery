# REST API Contract Specification: DataQuery (v1)

**Version**: `1.0.0`  
**Base URL**: `/api/v1`  
**Protocol**: HTTP/1.1 or HTTP/2 over TLS (or HTTP in local development)  
**Content-Type**: `application/json`

---

## 1. Global Standards & Error Envelope

All responses, both successful and erroneous, include a traceable request identifier header:
- `X-Request-ID: req_01h...`

### Consistent Error Envelope Format
When an endpoint returns a non-2xx status code (`400`, `404`, `422`, `500`, `503`), the response body **must** conform to the following JSON structure:

```json
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable explanation of what went wrong.",
    "details": {
      "field_name": ["Specific validation error message"]
    }
  },
  "request_id": "req_8f3d1b72a9"
}
```

### Standard Error Codes
| HTTP Status | Error Code | Description |
| :--- | :--- | :--- |
| `400` | `INVALID_INPUT` | Input query failed preliminary validation (length, character constraints). |
| `400` | `SQL_POLICY_VIOLATION` | Generated or submitted SQL violates security policies (non-SELECT, unauthorized table, etc.). |
| `400` | `SQL_SYNTAX_ERROR` | SQL string cannot be parsed into a valid Abstract Syntax Tree. |
| `404` | `RESOURCE_NOT_FOUND` | Requested entity (e.g. historical query ID) does not exist. |
| `422` | `UNPROCESSABLE_ENTITY` | Pydantic validation failure on request payload or LLM structured output. |
| `500` | `INTERNAL_SERVER_ERROR` | Unexpected server failure; detailed trace logged internally. |
| `500` | `DATABASE_EXECUTION_ERROR`| SQL execution failed on the database engine (e.g. division by zero, timeout). |
| `503` | `LLM_PROVIDER_UNAVAILABLE`| LLM upstream service is unreachable, timed out, or returning rate limit errors. |

---

## 2. Endpoint Specifications

### 2.1. System Health Check
Check operational readiness of the FastAPI server, PostgreSQL connection, and LLM provider.

- **Method / Path**: `GET /api/v1/health`
- **Authentication**: None
- **Query Parameters**: None

#### Response (200 OK)
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-10-25T10:48:00Z",
  "components": {
    "database": {
      "status": "connected",
      "latency_ms": 3.4
    },
    "llm": {
      "status": "ready",
      "provider": "anthropic",
      "model": "claude-3-5-sonnet-20241022"
    }
  }
}
```

#### Degraded Response (503 Service Unavailable)
```json
{
  "error": {
    "code": "DATABASE_UNAVAILABLE",
    "message": "Unable to establish connection to PostgreSQL engine.",
    "details": {
      "component": "database",
      "retry_after_seconds": 5
    }
  },
  "request_id": "req_9981bc2231"
}
```

---

### 2.2. Database Schema Catalog
Returns the public database schema definitions, columns, data types, and foreign key relations for the frontend Schema Explorer.

- **Method / Path**: `GET /api/v1/schema`
- **Authentication**: None
- **Query Parameters**: None

#### Response (200 OK)
```json
{
  "database": "dataquery_db",
  "as_of_date": "2024-11-01T00:00:00Z",
  "tables": [
    {
      "name": "customers",
      "description": "User customer profiles including geographic region.",
      "columns": [
        {"name": "id", "type": "INTEGER", "primary_key": true, "nullable": false},
        {"name": "name", "type": "VARCHAR(255)", "primary_key": false, "nullable": false},
        {"name": "email", "type": "VARCHAR(255)", "primary_key": false, "nullable": false},
        {"name": "region", "type": "VARCHAR(100)", "primary_key": false, "nullable": false},
        {"name": "created_at", "type": "TIMESTAMP", "primary_key": false, "nullable": false}
      ],
      "foreign_keys": []
    },
    {
      "name": "orders",
      "description": "Customer purchase orders and fulfillment status.",
      "columns": [
        {"name": "id", "type": "INTEGER", "primary_key": true, "nullable": false},
        {"name": "customer_id", "type": "INTEGER", "primary_key": false, "nullable": false},
        {"name": "order_date", "type": "TIMESTAMP", "primary_key": false, "nullable": false},
        {"name": "status", "type": "VARCHAR(50)", "primary_key": false, "nullable": false}
      ],
      "foreign_keys": [
        {"column": "customer_id", "references_table": "customers", "references_column": "id"}
      ]
    },
    {
      "name": "order_items",
      "description": "Individual items, quantities, and purchased prices for each order.",
      "columns": [
        {"name": "id", "type": "INTEGER", "primary_key": true, "nullable": false},
        {"name": "order_id", "type": "INTEGER", "primary_key": false, "nullable": false},
        {"name": "product_id", "type": "INTEGER", "primary_key": false, "nullable": false},
        {"name": "quantity", "type": "INTEGER", "primary_key": false, "nullable": false},
        {"name": "unit_price", "type": "NUMERIC(10,2)", "primary_key": false, "nullable": false}
      ],
      "foreign_keys": [
        {"column": "order_id", "references_table": "orders", "references_column": "id"},
        {"column": "product_id", "references_table": "products", "references_column": "id"}
      ]
    },
    {
      "name": "products",
      "description": "Product catalog listings with categories and current inventory.",
      "columns": [
        {"name": "id", "type": "INTEGER", "primary_key": true, "nullable": false},
        {"name": "name", "type": "VARCHAR(255)", "primary_key": false, "nullable": false},
        {"name": "category", "type": "VARCHAR(100)", "primary_key": false, "nullable": false},
        {"name": "price", "type": "NUMERIC(10,2)", "primary_key": false, "nullable": false},
        {"name": "inventory_count", "type": "INTEGER", "primary_key": false, "nullable": false},
        {"name": "created_at", "type": "TIMESTAMP", "primary_key": false, "nullable": false}
      ],
      "foreign_keys": []
    }
  ]
}
```

---

### 2.3. Curated Example Business Prompts
Returns sample questions grouped by category for quick testing in the UI.

- **Method / Path**: `GET /api/v1/examples`
- **Authentication**: None
- **Query Parameters**: None

#### Response (200 OK)
```json
{
  "categories": [
    {
      "name": "Revenue & Sales",
      "examples": [
        {"title": "Total Revenue", "question": "What is the total revenue across all completed orders?"},
        {"title": "Revenue by Region", "question": "Show total revenue broken down by customer region."},
        {"title": "Average Order Value", "question": "What is the average order value for delivered orders?"}
      ]
    },
    {
      "name": "Fulfillment & Orders",
      "examples": [
        {"title": "Undelivered Orders", "question": "How many orders are currently placed or shipped but not yet delivered?"},
        {"title": "Recent Orders", "question": "List orders placed in the last 30 days with customer names."}
      ]
    },
    {
      "name": "Product Performance",
      "examples": [
        {"title": "Top 5 Products", "question": "What are the top 5 best-selling products by quantity?"},
        {"title": "Low Inventory Items", "question": "Which products have fewer than 10 units in stock?"}
      ]
    }
  ]
}
```

---

### 2.4. Natural Language Analytics Query Execution
The primary entry point. Translates natural language into SQL, validates AST, executes read-only, and returns tabular data with an explanation.

- **Method / Path**: `POST /api/v1/query`
- **Authentication**: None
- **Headers**: `Content-Type: application/json`

#### Request Body
```json
{
  "question": "What are the top 3 customer regions by total revenue?",
  "include_explanation": true
}
```

#### Request Validation Rules
- `question`: Required string, min length: 3, max length: 500.
- `include_explanation`: Optional boolean, defaults to `true`.

#### Response (200 OK)
```json
{
  "query_id": "qry_01h8v1b5p7k",
  "question": "What are the top 3 customer regions by total revenue?",
  "sql": "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS total_revenue FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id WHERE o.status != 'cancelled' GROUP BY c.region ORDER BY total_revenue DESC LIMIT 3;",
  "columns": [
    {"name": "region", "type": "VARCHAR"},
    {"name": "total_revenue", "type": "NUMERIC"}
  ],
  "rows": [
    {"region": "North America", "total_revenue": 142500.00},
    {"region": "EMEA", "total_revenue": 98230.50},
    {"region": "APAC", "total_revenue": 76410.00}
  ],
  "row_count": 3,
  "execution_time_ms": 48,
  "explanation": "Calculated total revenue by summing item quantities multiplied by unit prices for each customer region, filtering out cancelled orders, and ordering results to return the top 3 regions.",
  "assumptions": [
    "Revenue definition excluded cancelled orders (status != 'cancelled').",
    "Customer region derived from customers.region."
  ]
}
```

#### Error Response: Security Policy Violation (400 Bad Request)
```json
{
  "error": {
    "code": "SQL_POLICY_VIOLATION",
    "message": "Generated query violated security policy: references forbidden table 'pg_shadow'.",
    "details": {
      "violated_rule": "TABLE_ALLOWLIST_VIOLATION",
      "disallowed_tables": ["pg_shadow"]
    }
  },
  "request_id": "req_1a2b3c4d5e"
}
```

#### Error Response: Database Execution Timeout (500 Internal Server Error)
```json
{
  "error": {
    "code": "DATABASE_EXECUTION_ERROR",
    "message": "Database query cancelled: execution exceeded 3000ms timeout.",
    "details": {
      "statement_timeout_ms": 3000
    }
  },
  "request_id": "req_8877665544"
}
```

---

### 2.5. Standalone SQL Validation Endpoint
Allows developer or UI verification of a raw SQL string against `sqlglot` security and structural rules without executing it against the database.

- **Method / Path**: `POST /api/v1/sql/validate`
- **Authentication**: None
- **Headers**: `Content-Type: application/json`

#### Request Body
```json
{
  "sql": "SELECT name, price FROM products WHERE price > 100 ORDER BY price DESC;"
}
```

#### Response (200 OK - Valid)
```json
{
  "is_valid": true,
  "sanitized_sql": "SELECT name, price FROM products WHERE price > 100 ORDER BY price DESC LIMIT 100;",
  "statement_type": "SELECT",
  "tables_referenced": ["products"],
  "columns_referenced": ["name", "price"],
  "has_limit": true,
  "errors": []
}
```

#### Response (200 OK - Policy Rejected)
```json
{
  "is_valid": false,
  "sanitized_sql": null,
  "statement_type": "DELETE",
  "tables_referenced": ["customers"],
  "columns_referenced": [],
  "has_limit": false,
  "errors": [
    "Statement type 'DELETE' is not permitted. Only 'SELECT' statements are allowed.",
    "Data mutation operations are strictly prohibited."
  ]
}
```

---

### 2.6. Query Execution History (Paginated)
Fetch past query executions logged in `dq_query_history`.

- **Method / Path**: `GET /api/v1/history`
- **Authentication**: None
- **Query Parameters**:
  - `page`: Optional integer, default `1`.
  - `page_size`: Optional integer, default `20`, max `50`.

#### Response (200 OK)
```json
{
  "page": 1,
  "page_size": 20,
  "total_count": 142,
  "items": [
    {
      "id": "qry_01h8v1b5p7k",
      "question": "What are the top 3 customer regions by total revenue?",
      "sql_preview": "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS total_revenue ...",
      "status": "SUCCESS",
      "execution_time_ms": 48,
      "row_count": 3,
      "created_at": "2026-10-25T10:45:12Z"
    }
  ]
}
```

---

### 2.7. Single Query Execution Details
Fetch complete details, SQL, and results summary for a specific historical query.

- **Method / Path**: `GET /api/v1/history/{id}`
- **Authentication**: None

#### Response (200 OK)
```json
{
  "id": "qry_01h8v1b5p7k",
  "question": "What are the top 3 customer regions by total revenue?",
  "sql": "SELECT c.region, SUM(oi.quantity * oi.unit_price) AS total_revenue FROM customers c JOIN orders o ON c.id = o.customer_id JOIN order_items oi ON o.id = oi.order_id WHERE o.status != 'cancelled' GROUP BY c.region ORDER BY total_revenue DESC LIMIT 3;",
  "status": "SUCCESS",
  "execution_time_ms": 48,
  "row_count": 3,
  "explanation": "Calculated total revenue by summing item quantities multiplied by unit prices for each customer region...",
  "created_at": "2026-10-25T10:45:12Z"
}
```

#### Error Response: Not Found (404 Not Found)
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Query history record with id 'qry_invalid' was not found.",
    "details": null
  },
  "request_id": "req_4040404040"
}
```
