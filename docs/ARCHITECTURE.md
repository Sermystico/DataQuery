# Architecture & System Design: DataQuery

## 1. System Overview

**DataQuery** is an AI-powered analytics assistant that translates natural language business questions into safe, read-only SQL queries against an e-commerce PostgreSQL database. It validates generated queries using an Abstract Syntax Tree (AST) parser, executes them under strict read-only constraints, formats the results, and produces a plain-English explanation of how the query answers the user's question.

### Project Goals
1. **Accessibility**: Allow non-technical stakeholders to ask plain-English questions about sales, customer behavior, and inventory.
2. **Deterministic Safety**: Treat all LLM outputs and user prompts as untrusted. Enforce multi-layered defense-in-depth across the application and database tiers.
3. **Interview Explainability**: Designed as a portfolio project for a student. Architecture choices prioritize clarity, testability, and standard patterns over premature abstraction or cleverness.
4. **Reproducibility**: Provide fixed analytical reference points (`ANALYTICS_AS_OF_DATE`), deterministic mock LLM drivers, and standalone Python ground-truth verification.

---

## 2. Business Definitions & Domain Context

To ensure consistency across prompt engineering, SQL generation, manual testing, and automated evaluation, the domain logic adheres to the following standardized definitions:

| Business Metric / Term | Technical Definition & Logic | Relevant Tables & Columns |
| :--- | :--- | :--- |
| **Revenue** | `SUM(order_items.quantity * order_items.unit_price)` for orders where `status != 'cancelled'`. *Note: Discounts or refunds are not modeled in the sample dataset; gross billed amount on non-cancelled orders equals revenue.* | `orders`, `order_items` |
| **Undelivered Orders** | Orders with `status IN ('placed', 'shipped')`. Delivered orders have `status = 'delivered'`, while cancelled orders have `status = 'cancelled'`. | `orders.status` |
| **Customer Region** | Geographical classification mapped directly from `customers.region` (e.g., `'North America'`, `'EMEA'`, `'APAC'`, `'LATAM'`). | `customers.region` |
| **Active Customer** | A customer who has placed at least one non-cancelled order. | `customers`, `orders` |
| **Average Order Value (AOV)** | Total Revenue divided by the count of distinct non-cancelled orders: `Revenue / COUNT(DISTINCT orders.id)`. | `orders`, `order_items` |

### Sample E-Commerce Database Schema
The database models a standard online store schema under the `public` schema:

1. **`customers`**
   - `id` (INT, PK): Unique customer identifier
   - `name` (VARCHAR): Full name
   - `email` (VARCHAR, UNIQUE): Customer email
   - `region` (VARCHAR): Region identifier (`'North America'`, `'EMEA'`, `'APAC'`, `'LATAM'`)
   - `created_at` (TIMESTAMP): Registration timestamp

2. **`products`**
   - `id` (INT, PK): Unique product identifier
   - `name` (VARCHAR): Product title
   - `category` (VARCHAR): Product category (e.g., `'Electronics'`, `'Apparel'`, `'Home'`)
   - `price` (NUMERIC(10, 2)): Standard listing unit price
   - `inventory_count` (INT): Current stock count in warehouse
   - `created_at` (TIMESTAMP): Catalog listing timestamp

3. **`orders`**
   - `id` (INT, PK): Unique order identifier
   - `customer_id` (INT, FK -> `customers.id`): Purchasing customer
   - `order_date` (TIMESTAMP): Timestamp order was placed
   - `status` (VARCHAR): Lifecycle status enum (`'placed'`, `'shipped'`, `'delivered'`, `'cancelled'`)

4. **`order_items`**
   - `id` (INT, PK): Unique line item identifier
   - `order_id` (INT, FK -> `orders.id`): Parent order
   - `product_id` (INT, FK -> `products.id`): Purchased item
   - `quantity` (INT): Units purchased (always > 0)
   - `unit_price` (NUMERIC(10, 2)): Price per unit at purchase time

5. **`dq_query_history`** *(Application internal metadata table, owned by `dq_owner`, accessible by `dq_app`, isolated from `dq_readonly`)*
   - `id` (VARCHAR/UUID, PK): Query identifier
   - `question` (TEXT): Natural language input
   - `generated_sql` (TEXT): Validated SQL statement
   - `status` (VARCHAR): `'SUCCESS'`, `'VALIDATION_ERROR'`, `'DB_ERROR'`
   - `execution_time_ms` (INT): Time taken in milliseconds
   - `created_at` (TIMESTAMP): Execution timestamp

---

## 3. High-Level Architecture & Request Flow

Every natural language query traverses an 8-stage pipeline before a response is returned to the user:

```
[ User Browser / React UI ]
             │  1. POST /api/v1/query { question: "..." }
             ▼
[ FastAPI App (api/v1/query) ]
             │  2. Input Validation (Pydantic: length, characters)
             ▼
[ SchemaContextService ] ───────► (Cached Schema Metadata & Business Rules)
             │  3. Formats System Prompt with Schema Context & Rules
             ▼
[ LLMService (LLMProvider) ] ───► Anthropic Claude / Deterministic Mock
             │  4. Returns Structured Output { sql, assumptions, ... }
             ▼
[ SQLSecurityValidator ] ───────► sqlglot AST Policy Engine
     ├── Single statement only?
     ├── Root is SELECT? (No INSERT, UPDATE, DROP, etc.)
     ├── Allowed tables only? (customers, products, orders, order_items)
     ├── Prohibited functions/system catalogs blocked?
     └── Enforce row LIMIT (defaults/caps at 100)
             │
             ├── [REJECT] ──────► Return 400 SQL_POLICY_VIOLATION
             ▼ [PASS]
[ DBExecutionService ] ────────► PostgreSQL Connection (Role: dq_readonly)
     ├── Set session read_only = true
     ├── Set statement_timeout = 3000ms
     └── Execute query & fetch rows (max 100)
             │
             ▼ 5. Raw Rows & Column Descriptions
[ ResultFormatterService ] ────► Sanitizes types, formats JSON table
             │
             ▼ 6. Generate Contextual Plain-English Explanation
[ LLMService / Rule Explainer ]
             │
             ▼ 7. Asynchronous Audit Log to dq_query_history (Role: dq_app)
[ Final JSON Response Envelope ]
             │  8. Returns { query_id, sql, columns, rows, explanation, ... }
             ▼
[ User Browser / React UI ]
```

### Detailed Pipeline Stages:
1. **Input Validation**: Fast preliminary validation on user input length (e.g. 5–500 characters), non-empty checks, and basic character safety.
2. **Schema Context Injection**: Generates prompt context including table schemas, foreign key relationships, business metrics (Revenue, Undelivered, Region), and reference `ANALYTICS_AS_OF_DATE`.
3. **Structured SQL Generation**: LLM provider produces a strictly structured JSON response conforming to a Pydantic contract containing the raw SQL, reasoning assumptions, and confidence score.
4. **SQL Parse & Policy Validation (`sqlglot`)**: The generated query is parsed into a syntax tree. The validator rigorously asserts that it is a single `SELECT` statement, references only permitted tables, contains no DDL/DML, and contains no dangerous functions.
5. **Read-Only Database Execution**: Executed using a scoped database session under the restricted `dq_readonly` role with a strict 3-second statement timeout.
6. **Result Formatting**: Database records are sanitized into standard tabular JSON containing column names, types, and value rows.
7. **Explanation Synthesis**: Produces an accessible explanation describing how the SQL translates to the user's intent.
8. **Response Packaging**: Wraps all output in a standardized, typed API envelope with unique `request_id`.

---

## 4. Component Responsibilities

The system is organized into modular layers with clear single responsibilities:

```
┌──────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│  FastAPI Endpoints (v1): Health, Schema, Query, Validate     │
└──────────────┬───────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────┐
│                     Services Layer                           │
│  QueryService: Coordinates generation, validation, execution │
│  SchemaService: Delivers introspected catalog & context      │
│  ResultFormatter: Cleans data types and tabular shapes       │
└──────┬───────────────────────┬───────────────────────┬───────┘
       │                       │                       │
┌──────▼────────┐       ┌──────▼────────┐       ┌──────▼───────┐
│   LLM Layer   │       │Security Layer │       │   DB Layer   │
│ LLMProvider   │       │SQLValidator   │       │Engine & Pool │
│  (Protocol)   │       │(sqlglot AST)  │       │dq_readonly   │
│ Anthropic/Mock│       │Policy Engine  │       │dq_app        │
└───────────────┘       └───────────────┘       └──────────────┘
```

### 1. `backend/app/api/v1`
- **`health.py`**: Health check probe returning database connectivity, LLM mode, and server status.
- **`schema.py`**: Returns the public database schema definitions and descriptions for the frontend schema viewer.
- **`query.py`**: Accepts natural language queries, coordinates pipeline execution, and returns results.
- **`sql.py`**: Standalone query validator endpoint allowing users or developers to test raw SQL against security policies.
- **`history.py`**: Read-only pagination over past queries logged in `dq_query_history`.

### 2. `backend/app/schemas`
- Pydantic models enforcing contract boundaries:
  - `query.py`: `QueryRequest`, `QueryResponse`, `QueryResultColumn`, `QueryResultRow`
  - `sql.py`: `SQLValidateRequest`, `SQLValidateResponse`
  - `llm.py`: `LLMSQLGenerationOutput` (structured output model with `sql`, `assumptions`, `confidence`)
  - `error.py`: `ErrorDetail`, `ErrorResponseEnvelope`

### 3. `backend/app/db`
- **`session.py`**: Synchronous SQLAlchemy 2.0 engine factory and connection pool management.
- **`roles.py`**: Context managers for checking out scoped connections:
  - `get_readonly_connection()`: Connects or switches role to `dq_readonly` with `SET default_transaction_read_only = on` and `SET statement_timeout = 3000`.
  - `get_app_connection()`: Connects as `dq_app` for persisting query execution telemetry into `dq_query_history`.

### 4. `backend/app/security`
- **`validator.py`**: AST parser using `sqlglot`. Verifies statement count == 1, expression type == `Select`, validates table identifiers against `ALLOWED_TABLES`, blocks system tables and dangerous built-ins.
- **`policies.py`**: Configuration defining table whitelist (`customers`, `products`, `orders`, `order_items`), max row limits (default 100, hard limit 500), and banned dialect functions (`pg_sleep`, `version`, etc.).

### 5. `backend/app/llm`
- **`protocol.py`**: `LLMProvider` Protocol defining standard signatures for `generate_sql(...)` and `generate_explanation(...)`.
- **`anthropic_provider.py`**: Implementation communicating with Anthropic API (e.g. Claude 3.5 Sonnet) using structured JSON output.
- **`mock_provider.py`**: Deterministic mock provider matching predefined questions to exact SQL queries and structured explanations, enabling zero-cost CI and offline test runs.
- **`prompts.py`**: Prompt engineering templates incorporating table schemas, foreign key diagrams, business definitions, and few-shot examples.

### 6. `backend/app/services`
- **`query_service.py`**: Orchestrates the end-to-end request pipeline.
- **`schema_service.py`**: Reads and caches database schema definitions and relationship metadata.
- **`formatter_service.py`**: Converts raw database row tuples into structured JSON payloads, safely handling date/time formatting and decimal conversions.

### 7. `backend/app/core`
- **`config.py`**: Pydantic `BaseSettings` reading environment variables (`DATABASE_URL`, `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `ANALYTICS_AS_OF_DATE`, `STATEMENT_TIMEOUT_MS`).
- **`constants.py`**: Global constants including business definition strings and standard error codes.
- **`errors.py`**: Custom domain exceptions (`SQLValidationError`, `DatabaseExecutionError`, `LLMGenerationError`).

---

## 5. Repository Layout

The repository is structured to maintain a clean separation between backend application code, database migrations, frontend UI, evaluation suites, and documentation:

```
DataQuery/
├── .git/
├── .gitignore
├── README.md
│
├── docs/                               # Phase 0 Architectural Documentation
│   ├── ARCHITECTURE.md                 # System overview, pipeline, layout, assumptions
│   ├── DECISIONS.md                    # Architecture Decision Records (ADRs)
│   ├── SECURITY.md                     # Threat model, controls, validator limits
│   ├── API_CONTRACT.md                 # REST API endpoints, schemas, error envelopes
│   └── EVAL_PLAN.md                    # 50+ test cases, correctness & security benchmarks
│
├── backend/                            # FastAPI Backend Application
│   ├── Dockerfile
│   ├── pyproject.toml / requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI application factory & middleware
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py           # v1 router aggregator
│   │   │       ├── health.py           # GET /health
│   │   │       ├── schema.py           # GET /schema
│   │   │       ├── examples.py         # GET /examples
│   │   │       ├── query.py            # POST /query
│   │   │       ├── sql.py              # POST /sql/validate
│   │   │       └── history.py          # GET /history, GET /history/{id}
│   │   ├── schemas/                    # Pydantic contract definitions
│   │   │   ├── __init__.py
│   │   │   ├── query.py
│   │   │   ├── schema.py
│   │   │   ├── sql.py
│   │   │   ├── llm.py
│   │   │   └── error.py
│   │   ├── db/                         # Database connection & session lifecycle
│   │   │   ├── __init__.py
│   │   │   ├── session.py              # Engine factory & pool
│   │   │   └── roles.py                # Role-scoped connection managers
│   │   ├── services/                   # Application orchestration services
│   │   │   ├── __init__.py
│   │   │   ├── query_service.py
│   │   │   ├── schema_service.py
│   │   │   ├── execution_service.py
│   │   │   └── formatter_service.py
│   │   ├── security/                   # SQL parsing and policy enforcement
│   │   │   ├── __init__.py
│   │   │   ├── validator.py            # sqlglot AST inspector
│   │   │   └── policies.py             # Whitelists, limits, rules
│   │   ├── llm/                        # LLM provider abstraction & clients
│   │   │   ├── __init__.py
│   │   │   ├── protocol.py             # LLMProvider Protocol
│   │   │   ├── anthropic_provider.py   # Anthropic Claude implementation
│   │   │   ├── mock_provider.py        # Deterministic mock implementation
│   │   │   └── prompts.py              # System prompts & few-shot examples
│   │   └── core/                       # Core configuration and exceptions
│   │       ├── __init__.py
│   │       ├── config.py               # Settings via pydantic-settings
│   │       ├── constants.py            # Constants & business definitions
│   │       └── errors.py               # Custom exceptions & handlers
│   │
│   ├── migrations/                     # Schema DDL & Alembic scripts
│   │   ├── env.py
│   │   └── versions/
│   ├── seed/                           # Seed datasets & initialization scripts
│   │   ├── seed_data.json              # Raw synthetic e-commerce data
│   │   └── seed_runner.py              # Database seeding script (dq_owner)
│   ├── scripts/                        # Management & setup scripts
│   │   └── init_db.sh / init_db.py     # Provision roles (dq_owner, dq_readonly, dq_app)
│   └── tests/                          # Backend test suite
│       ├── conftest.py
│       ├── test_validator.py           # Unit tests for sqlglot AST security rules
│       ├── test_api.py                 # Endpoint integration tests
│       └── test_db_roles.py            # Permission boundary & read-only tests
│
├── frontend/                           # React / TypeScript / Vite Client
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                        # Typed API client functions
│       │   └── client.ts
│       ├── components/                 # UI components
│       │   ├── Header.tsx
│       │   ├── QueryInput.tsx
│       │   ├── ExamplePrompts.tsx
│       │   ├── SchemaViewer.tsx
│       │   ├── ResultsTable.tsx
│       │   ├── SqlViewer.tsx
│       │   ├── ExplanationCard.tsx
│       │   └── ErrorBanner.tsx
│       ├── hooks/
│       │   └── useQuery.ts
│       └── types/
│           └── api.ts
│
└── eval/                               # Evaluation Framework & Verification
    ├── benchmark_cases.json            # 50+ evaluation cases (questions, categories, expected)
    ├── ground_truth.py                 # Pure Python verification script (seed dataset logic)
    ├── run_eval_pipeline.py            # Track 1: Mock-LLM regression test runner
    ├── run_eval_live.py                # Track 2: Live-LLM benchmark evaluation runner
    └── report_generator.py             # Formats test pass rates and latency statistics
```

---

## 6. Assumptions and Open Questions

### Assumptions
1. **Single Dialect Focus**: The application exclusively targets PostgreSQL 16+. The SQL parser (`sqlglot`) is configured specifically with dialect `'postgres'`.
2. **Deterministic Time Anchor**: Business analytics queries rely on relative dates ("last 30 days", "this month"). To make results completely reproducible regardless of current date, queries will evaluate against a fixed configuration `ANALYTICS_AS_OF_DATE = '2024-11-01T00:00:00Z'` provided in prompt context.
3. **Database Size & Performance**: The sample e-commerce dataset contains moderate row counts (~10,000 orders) suitable for direct read execution within a 3-second statement timeout without dedicated analytical columnar indexing.
4. **Synchronous Execution Model**: Queries are expected to execute in sub-second to low-second times. A synchronous request-response flow in FastAPI is chosen to maintain codebase simplicity for portfolio review.
5. **Role Separation on Single DB Instance**: The three database roles (`dq_owner`, `dq_readonly`, `dq_app`) operate within a single PostgreSQL database instance, using PostgreSQL grant privileges and session variables for boundary enforcement.

### Open Questions
1. **Dialect-Specific Function Whitelisting**: Should date-truncation functions like `DATE_TRUNC` and math functions like `ROUND` be explicitly whitelisted or permitted by default under standard `Select` expressions? *(Tentative resolution: Allow standard pure scalar/aggregate functions; explicitly block system/catalog inspection and administrative functions).*
2. **Query History Isolation**: Should `dq_query_history` be stored in the same database under a separate schema (`app.query_history`) or in the `public` schema with explicit table-level `REVOKE SELECT ON dq_query_history FROM dq_readonly`? *(Tentative resolution: Table-level revoke in public schema with dq_owner granting permissions only to dq_app).*
3. **Frontend Visualization**: Beyond tabular display, should simple bar/line chart rendering be supported for aggregated groupings (e.g. revenue by month) in later phases?
