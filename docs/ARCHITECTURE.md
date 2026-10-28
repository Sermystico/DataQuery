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

5. **`payments`**
   - `id` (INT, PK): Unique payment transaction identifier
   - `order_id` (INT, FK -> `orders.id`): Paid order
   - `amount` (NUMERIC(10, 2)): Payment transaction amount
   - `method` (VARCHAR): Payment method (`'credit_card'`, `'bank_transfer'`, etc.)
   - `status` (VARCHAR): Payment status (`'completed'`, `'pending'`, `'failed'`)
   - `paid_at` (TIMESTAMP): Payment timestamp

6. **`app.query_history`** *(Application internal audit table, owned by `dq_owner`, accessible by `dq_app`, isolated from `dq_readonly`)*
   - `id` (SERIAL, PK): Query identifier
   - `request_id` (VARCHAR): Unique request correlation ID
   - `question` (TEXT): Natural language input
   - `status` (VARCHAR): `'success'`, `'unsupported'`, `'rejected'`, `'error'`
   - `sql` (TEXT): Validated and normalized SQL statement (or attempted SQL)
   - `row_count` (INT): Number of result rows returned
   - `error_code` (VARCHAR): Standardized error code if applicable
   - `duration_ms` (FLOAT): Total execution time in milliseconds
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
[ LLMProvider (Factory) ] ─────► Mock / Ollama / Anthropic / Gemini
             │  4. Returns Structured Output { sql, supported, reason, ... }
             ▼
[ SQLSecurityValidator ] ───────► sqlglot AST Policy Engine
     ├── Single statement only?
     ├── Root is SELECT? (No INSERT, UPDATE, DROP, etc.)
     ├── Allowed tables only? (customers, products, orders, order_items, payments)
     ├── Prohibited functions/system catalogs blocked?
     └── Enforce row LIMIT (defaults/caps at 100, fetches max_rows + 1)
             │
             ├── [REJECT] ──────► Return 400 VALIDATION_REJECTED
             ▼ [PASS]
[ QueryExecutor ] ─────────────► PostgreSQL Connection (Role: dq_readonly)
     ├── Set transaction read_only = true
     ├── Set statement_timeout = 3000ms
     └── Execute query & fetch rows (detects truncation at max_rows + 1)
             │
             ▼ 5. Raw Rows & Column Descriptions
[ ResultFormatter ] ───────────► Sanitizes types, converts Decimal to float, chart hints
             │
             ▼ 6. Generate Contextual Plain-English Explanation
[ Explainer (LLM / Rule) ] ────► Strict data-only invariant (max 20 rows, fallback)
             │
             ▼ 7. Audit Log to app.query_history (Role: dq_app)
[ Final JSON Response Envelope ]
             │  8. Returns { status, question, sql, columns, rows, answer, ... }
             ▼
[ User Browser / React UI ]
```

### Detailed Pipeline Stages:
1. **Input Validation**: Fast preliminary validation on user input length (e.g. 5–500 characters), non-empty checks, and basic character safety.
2. **Schema Context Injection**: Generates prompt context including 5 permitted table schemas, foreign key relationships, business metrics (Revenue, Undelivered, Region), and reference `ANALYTICS_AS_OF_DATE`.
3. **Structured SQL Generation**: LLM provider produces a strictly structured JSON response conforming to the `SQLGeneration` Pydantic contract containing SQL, `supported` boolean flag, and reasoning.
4. **SQL Parse & Policy Validation (`sqlglot`)**: The generated query is parsed into an AST. The validator asserts that it is a single `SELECT` statement, references only permitted tables, contains no DDL/DML, checks columns via qualification, strips comments, and injects/clamps LIMIT to `max_rows + 1`. Returns opaque `ValidatedSQL` token.
5. **Read-Only Database Execution**: Executed using `readonly_engine` under the restricted `dq_readonly` role with `SET TRANSACTION READ ONLY` and 3-second statement timeout.
6. **Result Formatting**: Database records are sanitized into standard tabular JSON, converting Decimals to float and computing deterministic `ChartHint` recommendations.
7. **Explanation Synthesis**: Produces an accessible explanation describing how the result answers the question, with rule-based fallback if the LLM explanation fails.
8. **Response Packaging & Audit**: Persists execution metrics to `app.query_history` via `app_engine` (`dq_app` role) and returns standard typed `QueryResponse`.

---

## 4. Component Responsibilities

The system is organized into modular layers with clear single responsibilities:

```
┌──────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│  FastAPI Endpoints (v1): Health, Schema, Query, History, Ex. │
└──────────────┬───────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────┐
│                     Services Layer                           │
│  QueryService: Coordinates generation, validation, execution │
│  ResultFormatter: Cleans data types, decimal conversion      │
│  Explainer: Generates data explanations with fallback        │
└──────┬───────────────────────┬───────────────────────┬───────┘
       │                       │                       │
┌──────▼────────┐       ┌──────▼────────┐       ┌──────▼───────┐
│   LLM Layer   │       │Security Layer │       │   DB Layer   │
│ LLMProvider   │       │sql_validator  │       │Engines & Pool│
│  (Protocol)   │       │query_executor │       │dq_readonly   │
│Mock/Ollama/   │       │policy engine  │       │dq_app        │
│Anthropic/Gem. │       │ValidatedSQL   │       │history_repo  │
└───────────────┘       └───────────────┘       └──────────────┘
```

### 1. `backend/app/api/v1`
- **`health.py`**: Health check probe returning database connectivity, active LLM provider, and server status.
- **`schema.py`**: Returns the public database schema definitions, columns, and business definitions for the frontend.
- **`query.py`**: Accepts natural language queries, coordinates 7-step pipeline execution, and returns standard envelope.
- **`sql.py`**: Standalone query validator endpoint allowing users or developers to test raw SQL against security policies.
- **`history.py`**: Read-only pagination over past queries logged in `app.query_history`.
- **`examples.py`**: Returns curated prompt exemplars with category tags to assist user query formulation.

### 2. `backend/app/schemas`
- Pydantic models enforcing contract boundaries:
  - `query.py`: `QueryRequest`, `QueryResponse`, `ChartHint`
  - `sql.py`: `SQLValidateRequest`, `SQLValidateResponse`
  - `history.py`: `HistoryResponse`, `HistoryItem`
  - `examples.py`: `ExamplesResponse`, `ExampleCategory`, `ExampleItem`

### 3. `backend/app/db`
- **`engines.py`**: Connection pool management creating two distinct SQLAlchemy engines:
  - `readonly_engine`: Bound to `dq_readonly` for query execution.
  - `app_engine`: Bound to `dq_app` for persisting query execution telemetry into `app.query_history`.
- **`history_repo.py`**: Data access functions for recording and fetching history records using `app_engine`.

### 4. `backend/app/security`
- **`sql_validator.py`**: AST parser using `sqlglot`. Verifies statement count == 1, expression type == `Select`, validates table identifiers against `ALLOWED_TABLES`, blocks system tables, qualifies columns, clamps LIMIT to `max_rows + 1`, and produces opaque `ValidatedSQL` token.
- **`query_executor.py`**: Executes `ValidatedSQL` instances strictly under `dq_readonly` with `SET TRANSACTION READ ONLY;`, `statement_timeout`, and truncation detection.
- **`policy.py`**: Single source of truth for table whitelist (`customers`, `products`, `orders`, `order_items`, `payments`), column allowlist, function allowlist, and business definitions.

### 5. `backend/app/llm`
- **`base.py`**: `LLMProvider` Protocol and `SQLGeneration` Pydantic model.
- **`factory.py`**: Central provider instantiation supporting `mock`, `ollama`, `anthropic`, and `gemini`.
- **`mock_provider.py`**: Deterministic mock provider matching predefined questions to exact SQL queries and structured explanations, enabling zero-cost CI and offline test runs.
- **`ollama_provider.py`**: Local model integration via Ollama REST API (e.g. `llama3.2:latest`) with zero API costs.
- **`anthropic_provider.py`**: Implementation communicating with Anthropic API (e.g. Claude 3.5 Sonnet) using structured tool calling.
- **`gemini_provider.py`**: Official Google `google-genai` SDK implementation with rate-limiting retries and JSON response schema.
- **`prompts.py`** & **`schema_context.py`**: Prompt engineering templates incorporating table schemas, foreign key diagrams, business definitions, and few-shot examples.

### 6. `backend/app/services`
- **`query_service.py`**: Orchestrates the 7-step natural language query workflow.
- **`formatter.py`**: Converts raw database row tuples into structured JSON payloads, safely handling date/time formatting and Decimal-to-float conversions.
- **`explainer.py`**: Produces plain-English explanations with strict data-only bounds and a deterministic fallback template.

### 7. `backend/app/core`
- **`config.py`**: Pydantic `BaseSettings` reading environment variables with typed secrets and connection URL properties.
- **`errors.py`**: Custom domain exceptions (`AppError`, `ValidationRejected`, `UnsupportedQuestion`, `LLMUnavailable`, `DatabaseUnavailable`, `QueryTimeout`, `NotFound`).
- **`logging.py`**: Structured logger configuration ensuring secrets are never leaked into log output.

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
