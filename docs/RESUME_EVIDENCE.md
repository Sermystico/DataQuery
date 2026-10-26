# DataQuery — Resume Evidence & Verification Audit

This document provides auditable evidence, exact counts, architectural references, and test linkages verifying the technical capabilities and deliverables of the **DataQuery** platform.

---

## Executive Summary of Claims

| Claim / Capability | Target | Actual Count | Status | Primary Artifacts & Test Evidence |
| :--- | :---: | :---: | :---: | :--- |
| **Business Query Library** | 20+ | **32** canonical queries | **MET** | [golden_queries.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/app/llm/golden_queries.py), [test_eval_ground_truth.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/evaluation/test_eval_ground_truth.py) |
| **REST API Endpoints** | 5+ | **7** endpoints | **MET** | [router.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/app/api/v1/router.py), [test_api_v1.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_api_v1.py) |
| **Automated Evaluation Cases** | 50+ | **52** benchmark cases | **MET** | [cases.yaml](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/cases.yaml), [latest.md](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/reports/latest.md), [run_eval.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/run_eval.py) |
| **Test Suite Quality & Pass Rate** | >85% cov | **92%** coverage (289 passed) | **MET** | [pytest.ini](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/pytest.ini), [backend/tests/](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/) |
| **Docker Orchestration** | 3 services | **3** containers (healthy) | **MET** | [docker-compose.yml](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/docker-compose.yml), [Dockerfile](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/Dockerfile) |

---

## 1. Business Query Library (32 Canonical Queries)

### Claim: **MET**
The system implements **32 canonical analytical queries** covering e-commerce analytics, outperforming the target of 20+.

### Category Breakdown
Defined in [golden_queries.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/app/llm/golden_queries.py):
1. **Aggregations (6 queries)**: Total revenue (`AGG-01`), average order value (`AGG-02`), unique customers (`AGG-03`), items per order (`AGG-04`), completed orders (`AGG-05`), successful payment sums (`AGG-06`).
2. **Grouping & Segmentation (6 queries)**: Revenue by product category (`GRP-01`), customer spend by region (`GRP-02`), order status distribution (`GRP-03`), orders per customer (`GRP-04`), payment method breakdown (`GRP-05`, `GRP-06`).
3. **Date & Trend Analysis (5 queries)**: Orders in 2024 (`DAT-01`), rolling 30-day order counts (`DAT-02`), summer signups (`DAT-03`), monthly order volume (`DAT-04`), month-over-month revenue comparison (`DAT-05`).
4. **Filtering & Slicing (4 queries)**: EMEA customer list (`FLT-01`), premium products >$100 (`FLT-02`), cancelled order audit (`FLT-03`), single-day orders (`FLT-04`).
5. **Multi-Table Joins (3 queries)**: Customer name with order total and status (`JOIN-01`), product units sold with outer join (`JOIN-02`), 5-table audit join (`JOIN-03`).
6. **Window Functions (3 queries)**: Category price ranking via `ROW_NUMBER()` (`WIN-01`), dense ranking (`WIN-02`), order interval lead/lag analysis (`WIN-03`).
7. **Common Table Expressions (2 queries)**: Regional revenue with CTE (`CTE-01`), customer VIP spend segmentation (`CTE-02`).
8. **Fulfillment & Lifecycle (3 queries)**: Undelivered pipeline count (`FUL-01`), recent delivered deliveries (`FUL-02`), payment latency (`FUL-03`).

### Distinction: Mock Questions vs. Live-Verified Accuracy
- **Deterministic Mock Mode (Track 1)**: In mock mode, the mock provider maps question signatures directly to canonical golden SQL. This evaluates the end-to-end pipeline: SQL AST parsing, security policy enforcement, read-only transaction scoping, execution under `dq_readonly`, result formatting, and rule-based fallback explanations. Verified: **32/32 (100.0%) passed** in 1.1s.
- **Independent Python Ground Truth**: Every single query's expected columns and values are calculated in pure Python directly from the deterministic dataset in [ground_truth.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/ground_truth.py) without executing SQL. Float values are compared with an absolute numeric tolerance of `0.01`.
- **Live LLM Accuracy (Track 2)**: Using `--provider anthropic`, the evaluation suite submits unconstrained natural language prompts to Claude 3.5 Sonnet. The generated SQL must pass `validate_sql()` and match the independent Python calculation within 0.01 tolerance. This decouples pipeline correctness from upstream LLM semantic precision.

---

## 2. REST API Endpoints (7 Implemented Endpoints)

### Claim: **MET**
The platform implements **7 production REST endpoints** under `/api/v1` and root, exceeding the 5+ target.

### Implemented Endpoints
Documented in [router.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/app/api/v1/router.py) and verified via [test_api_v1.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_api_v1.py):

| Method | Endpoint | Description | Verification Evidence |
| :---: | :--- | :--- | :--- |
| `POST` | `/api/v1/query` | Translates NL question to SQL, validates AST, executes read-only, generates explanation and chart hints, logs audit history. | [test_query_workflow.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_query_workflow.py) |
| `POST` | `/api/v1/sql/validate` | Dedicated SQL security and AST syntax validator; exposes allowlist policies and normalization without executing SQL. | [test_sql_validator.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/unit/test_sql_validator.py) |
| `GET` | `/api/v1/schema` | Exposes database catalog metadata for the 5 analytics tables (`customers`, `products`, `orders`, `order_items`, `payments`), including primary keys and foreign keys. | [test_schema_endpoint.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_schema_endpoint.py) |
| `GET` | `/api/v1/examples` | Returns curated prompt exemplars with category tags to assist user query formulation. | [test_examples_endpoint.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_examples_endpoint.py) |
| `GET` | `/api/v1/history` | Audit log endpoint returning recent query executions, execution times, status codes, and chart hints. | [test_history_repo.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_history_repo.py) |
| `GET` | `/api/v1/health` | Service and database health check verifying PostgreSQL connection pool latency and readiness. | [test_health.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_health.py) |
| `GET` | `/health` | Root alias for load balancers and container orchestrators. | [test_health.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/integration/test_health.py) |

---

## 3. Automated Evaluation Cases (52 Benchmark Cases)

### Claim: **MET**
The evaluation suite comprises **52 comprehensive cases** defined in [eval/cases.yaml](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/cases.yaml), exceeding the 50+ requirement.

### Case Breakdown by Category
1. **Correctness Cases (32 cases: `COR-01` to `COR-32`)**:
   - Covers all 32 golden queries across joins, aggregations, window functions, and date truncations.
   - Evaluated against pure Python ground truth ([ground_truth.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/ground_truth.py)).
   - Invariant verification: passes with 0.01 tolerance; invariant database row count checked before and after.
2. **Security & Adversarial Cases (14 cases: `SEC-01` to `SEC-14`)**:
   - Direct DDL injection (`DROP TABLE orders`, `TRUNCATE customers`).
   - DML mutation injection (`INSERT INTO customers`, `UPDATE products`, `DELETE FROM orders`).
   - Multi-statement command chaining (`SELECT 1; DROP TABLE products;`).
   - System catalog exfiltration (`SELECT * FROM pg_catalog.pg_user`, `information_schema.tables`).
   - File system access functions (`pg_read_file`, `pg_write_file`).
   - Administrative function calls (`pg_sleep(10)`, `pg_terminate_backend`).
   - Disallowed SQL constructs (disallowed window functions, subquery recursion).
   - Prompt injection attacks attempting to force schema exposure or bypass filters.
   - SQL comment evasion (`SELECT 1 --\n; DROP TABLE orders`).
3. **Failure & Resilience Cases (6 cases: `FAIL-01` to `FAIL-06`)**:
   - Upstream LLM provider outage (`FAIL-01` -> returns HTTP 503 / friendly envelope).
   - Syntactically malformed SQL from LLM (`FAIL-02` -> rejected safely without runtime crash).
   - Dangerous multi-statement SQL from LLM (`FAIL-03` -> rejected by AST policy).
   - Ambiguous or unsupported business domain question (`FAIL-04` -> returns `status="unsupported"`).
   - Explanation model failure while SQL execution succeeds (`FAIL-05` -> falls back gracefully to deterministic rule-based template).
   - Pathological query statement timeout (`FAIL-06` -> PostgreSQL `statement_timeout` cancels execution at 100ms with typed `QueryTimeout` exception).

### Verification Evidence
- [eval/reports/latest.json](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/reports/latest.json): Full execution trace with 52/52 passed (100.0%).
- [eval/reports/latest.md](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/reports/latest.md): Human-readable audit report generated automatically by [run_eval.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/eval/run_eval.py).
- Negative control test in [test_negative_control.py](file:///c:/Users/YAJAT/Documents/Projects/DataQuery/backend/tests/evaluation/test_negative_control.py): verifies that intentional corruption of numbers, columns, or rows reliably triggers failure.

---

## 4. Code Quality & Test Coverage Evidence

### Claim: **MET**
- **Backend Test Suite**: **289 passed**, 1 skipped (Anthropic live key check), **92% line coverage** across all modules.
- **Frontend Test Suite**: **26 passed** across 5 test suites with React Testing Library and Vitest.
- **Frontend Build**: Zero-error production build (`tsc -b && vite build`) producing optimized production assets.
- **Linting & Formatting**: Clean Ruff audit across backend and evaluation codebase (`ruff check backend eval`).

---

## 5. Security & Isolation Verification

### Claim: **MET**
1. **Four-Layer Defense-in-Depth**:
   - *Layer 1 (Prompt & Schema Sandbox)*: System prompt contains only allowed schemas; forbids DDL/DML.
   - *Layer 2 (AST Policy Validation)*: AST parser inspects statement type, table names, columns, functions, and comment stripping via `sqlglot`.
   - *Layer 3 (Database Role Privilege Boundary)*: Queries run strictly under `dq_readonly` PostgreSQL user (`CONNECT`, `USAGE`, `SELECT` on 5 tables only; no `pg_catalog` or temporary table creation).
   - *Layer 4 (Transaction Runtime Limits)*: `SET TRANSACTION READ ONLY;`, `SET LOCAL statement_timeout = 3000;`, and row limit clamping to 100 rows.
2. **Secret Hygiene**:
   - `.env` excluded by `.gitignore` and `.dockerignore`.
   - Verified zero git commits containing `.env` or plain-text secrets in repository history.
   - Passwords and API keys typed via Pydantic `SecretStr`.
