# Architecture Decision Records (ADRs): DataQuery

This document records the architectural and design decisions made for the DataQuery platform. Each record details the context, the decision made, the trade-offs, and why alternative options were rejected.

---

## ADR-001: Use `sqlglot` for SQL AST Parsing and Validation

### Status
Accepted

### Context
Natural language to SQL systems inherently generate untrusted SQL strings. We must rigorously enforce security and structural rules: ensuring the query is strictly a single `SELECT` statement, contains no mutations or DDL (`INSERT`, `UPDATE`, `DROP`, `ALTER`), references only allowed tables, and contains no dangerous functions or nested system queries.

### Decision
Use **`sqlglot`** as our primary SQL parser and Abstract Syntax Tree (AST) inspection engine.

### Alternatives Considered
1. **Regular Expressions / Keyword String Matching**:
   - *Why rejected*: Extremely brittle and vulnerable to trivial obfuscation bypasses (e.g., inline SQL comments `SELECT/*comment*/1`, subqueries, nested CTEs, string literals containing keywords, unusual whitespace, or quoted identifiers).
2. **`pglast` (libpg_query C bindings)**:
   - *Why rejected*: While it provides 100% exact PostgreSQL grammar coverage, it depends on C extensions wrapping PostgreSQL source code. This introduces compilation dependencies, cross-platform build friction on Windows/macOS/Linux, and lower AST ergonomics for student interview explanation compared to pure Python.

### Rationale & Trade-offs
- `sqlglot` is pure Python, installs seamlessly across all operating systems, and parses PostgreSQL dialect into a clean, inspectable AST hierarchy (`exp.Select`, `exp.Table`, `exp.Literal`).
- Allows precise traversal of all table expressions to enforce table allowlisting.
- Can transparently rewrite or inject `LIMIT` clauses into the AST before query execution.
- *Trade-off*: `sqlglot` may occasionally lag on cutting-edge PostgreSQL dialect additions; however, our e-commerce query surface uses standard, mature SQL features.

### Student Interview Talking Point
> *"Regex matching is fundamentally flawed for SQL security because SQL is a context-free grammar with support for comments, quotes, and nested expressions. By parsing queries into an Abstract Syntax Tree using `sqlglot`, we can inspect the true semantic nodes of the query rather than relying on brittle text patterns."*

---

## ADR-002: Three-Tier Database Role Architecture (`dq_owner`, `dq_readonly`, `dq_app`)

### Status
Accepted

### Context
Defense-in-depth requires that even if application-level SQL validation fails or is bypassed, the database itself must enforce strict authorization boundaries. Furthermore, internal application tables (such as query audit history) must be protected from user-generated queries.

### Decision
Implement three dedicated PostgreSQL roles with explicit privilege boundaries:

1. **`dq_owner`**:
   - Schema owner.
   - Used exclusively for migrations, DDL, and database seeding.
   - Never used by backend request handling.
2. **`dq_readonly`**:
   - The connection role used strictly to execute generated analytics queries.
   - Granted `SELECT` permission **only** on analytics tables (`customers`, `products`, `orders`, `order_items`).
   - Explicitly denied access to system catalogs (`pg_shadow`, `pg_authid`) and application tables (`dq_query_history`).
   - Configured with session defaults: `SET default_transaction_read_only = on` and `SET statement_timeout = '3000ms'`.
3. **`dq_app`**:
   - Used by the FastAPI application for normal operational tasks.
   - Granted read and write access to `dq_query_history` to log execution telemetry.
   - Has read access to analytical schema metadata.

### Alternatives Considered
- **Single Database User with Superuser/Full Privileges**:
  - *Why rejected*: A severe security vulnerability. Any SQL injection or parser bypass could drop tables, modify customer records, or read database credentials.
- **Single Read-Only User**:
  - *Why rejected*: Would prevent the application from logging query history, audit metrics, or session states into the database.

### Rationale & Trade-offs
- Provides structural defense-in-depth: the database kernel enforces read-only access even if an attacker tricks the parser.
- Separates analytics data from application operational data.
- *Trade-off*: Requires maintaining role provisioning scripts in migrations/docker initialization.

### Student Interview Talking Point
> *"We follow the Principle of Least Privilege by separating database roles: migrations run under `dq_owner`, application logs are written by `dq_app`, and generated SQL is executed strictly under `dq_readonly` with database-level read-only flags and execution timeouts."*

---

## ADR-003: Synchronous SQLAlchemy 2.0 with `psycopg` 3 and Synchronous FastAPI Endpoints

### Status
Accepted

### Context
FastAPI supports both synchronous (`def`) and asynchronous (`async def`) path operations. Similarly, SQLAlchemy 2.0 supports async drivers (`asyncpg`) and sync drivers (`psycopg` 3). We must decide the concurrency architecture for the backend.

### Decision
Adopt **synchronous SQLAlchemy 2.0** with the **`psycopg` 3** driver and standard synchronous (`def`) FastAPI endpoints running on standard threadpool workers.

### Alternatives Considered
- **AsyncIO (`asyncpg` + `async def`)**:
  - *Why rejected*: Adds mental overhead and complexity regarding async context managers, session scoping, event loop blocking (e.g. during CPU-bound AST parsing in `sqlglot`), and difficult-to-debug "greenlet spawn" exceptions. For a student portfolio project, the added complexity yields negligible benefit given our query volume.

### Rationale & Trade-offs
- FastAPI automatically offloads synchronous endpoints (`def endpoint(...)`) to an internal `anyio` threadpool worker, avoiding blocking the main event loop.
- `psycopg` 3 is the modern, battle-tested standard PostgreSQL driver for Python.
- Synchronous database connections and session transactions are clean, easy to read, and simple to reason about during technical interview walkthroughs.
- *Trade-off*: Lower maximum theoretical concurrent connections compared to async under massive IO load, but completely sufficient for portfolio analytics workloads.

### Student Interview Talking Point
> *"We chose synchronous SQLAlchemy 2.0 and psycopg 3 because it eliminates async session lifecycle pitfalls while FastAPI automatically runs synchronous endpoints in a threadpool. For an analytics service doing CPU-bound AST validation, code clarity and debuggability far outweigh micro-optimizations."*

---

## ADR-004: LLM Provider Protocol with Anthropic Client and Deterministic Mock

### Status
Accepted

### Context
The application relies on an LLM to generate SQL and explanations. However, tests, CI/CD pipelines, and local development must function reliably without requiring an active paid API key, without incurring API costs, and without network flakiness.

### Decision
Define a strict Python `typing.Protocol` named `LLMProvider` that specifies the contract for LLM operations. Provide two concrete implementations:
1. **`AnthropicProvider`**: Communicates with Anthropic API (e.g. Claude 3.5 Sonnet) using structured JSON output.
2. **`MockLLMProvider`**: A deterministic provider containing a dictionary of canonical question-to-SQL mappings and realistic mock explanations.

```python
class LLMProvider(Protocol):
    def generate_sql(self, question: str, schema_context: str) -> LLMSQLGenerationOutput: ...
    def generate_explanation(self, question: str, sql: str, results_summary: str) -> str: ...
```

### Alternatives Considered
- **Direct Anthropic SDK calls embedded in endpoints**:
  - *Why rejected*: Tightly couples the application to a single vendor and prevents unit testing without live API keys.
- **LangChain / LlamaIndex framework**:
  - *Why rejected*: High abstraction overhead ("magic"), heavy dependency tree, rapid breaking changes, and difficult to explain in an interview. Writing a clean 20-line protocol demonstrates first-principles architectural understanding.

### Rationale & Trade-offs
- Enables instant, zero-cost CI testing and reproducible evaluation test suites.
- Decouples business logic from specific LLM providers (allows swapping to OpenAI or local Ollama if desired).
- Allows mocking edge cases (malformed JSON, hallucinations, timeouts) deterministically.

### Student Interview Talking Point
> *"By implementing the Dependency Inversion Principle with a Python Protocol, we decouple the query engine from Anthropic. This lets us swap in a deterministic MockProvider for zero-cost offline testing, CI/CD verification, and reproducible grading."*

---

## ADR-005: Structured LLM Output Validated by Pydantic

### Status
Accepted

### Context
LLMs frequently add unsolicited commentary, markdown code blocks (````sql ... ````), or conversational text when prompted to return SQL. Passing unstructured strings directly into SQL parsers causes syntax parsing errors and unpredictable failures.

### Decision
Instruct the LLM to output a strict JSON schema and validate the raw text output against a Pydantic model (`LLMSQLGenerationOutput`) before passing the SQL string to the security validator:

```python
class LLMSQLGenerationOutput(BaseModel):
    sql: str
    assumptions: list[str]
    confidence: float
    explanation_summary: str
```

### Alternatives Considered
- **Unstructured Prompting with Regex Markdown Stripping**:
  - *Why rejected*: Regex extraction of code fences (````sql(.*?)````) fails when models omit fences, include multiple snippets, or embed explanations inside the code block.
- **Function Calling / Tool Calling API exclusively**:
  - *Why supported as underlying mechanism*: Where supported, structured tool calling outputs JSON that directly validates against this Pydantic schema.

### Rationale & Trade-offs
- Pydantic provides type coercion, validation errors, and clean error envelopes.
- Captures not just the SQL, but the model's analytical assumptions (e.g., "Assumed cancelled orders should be excluded").
- Provides a clean fallback error if the model produces malformed JSON.

### Student Interview Talking Point
> *"We use structured outputs validated by Pydantic as the first gatekeeper. Before any SQL touches the parser, we assert that the model returned a valid JSON schema containing the query, the model's confidence, and explicit business assumptions."*

---

## ADR-006: Fixed `ANALYTICS_AS_OF_DATE` for Deterministic Relative Dates

### Status
Accepted

### Context
Users frequently ask time-relative business questions such as *"How much revenue was generated in the last 30 days?"* or *"How many orders were placed this month?"*. In SQL, these typically resolve to expressions like `CURRENT_DATE - INTERVAL '30 days'`. In a static demo database seeded with fixed synthetic dates, evaluating relative to `CURRENT_DATE` produces empty result sets after 30 days.

### Decision
Establish a fixed analytical reference date constant:
`ANALYTICS_AS_OF_DATE = "2024-11-01T00:00:00Z"`

This constant is:
1. Injected into the LLM system prompt: *"Assume current analytical reference date is '2024-11-01'. Interpret 'last 30 days' as between '2024-10-02' and '2024-11-01'."*
2. Configurable via environment variables for testing different epochs.

### Alternatives Considered
- **Dynamic seed data re-stamping on every container start**:
  - *Why rejected*: Makes static ground truth datasets invalid and destroys reproducible evaluation baselines.
- **Disallowing relative date questions**:
  - *Why rejected*: Unrealistic for real-world e-commerce analytics where relative time queries constitute 40%+ of typical questions.

### Rationale & Trade-offs
- Guarantees 100% deterministic test and evaluation results across months and years.
- Faithfully simulates how enterprise data warehouses handle fixed-period snapshots and financial fiscal dates.

### Student Interview Talking Point
> *"In production analytics, relative queries against static seed data drift over time. By establishing a fixed analytical reference date, we ensure that queries like 'revenue in the last 30 days' always produce deterministic, reproducible results for our automated eval harness."*

---

## ADR-007: Expected Eval Results Computed Independently in Python from Seed Dataset

### Status
Accepted

### Context
To evaluate whether the AI assistant generated the correct answer, we need a "ground truth" standard. A naive approach is to write reference SQL queries and compare the LLM's SQL string or output to the reference SQL. However, if the reference SQL contains a logic flaw, the eval harness is flawed. Furthermore, direct string comparison fails when valid SQL uses different joins or aliases.

### Decision
Compute all expected evaluation results **independently in pure Python** (using `pandas` or native Python list comprehensions) directly from the raw `seed_data.json` source files, completely independent of the SQL engine.

### Alternatives Considered
- **SQL-to-SQL Text Diffing**:
  - *Why rejected*: Multiple distinct SQL queries are semantically equivalent (e.g., `JOIN` ordering, subquery vs CTE, `WHERE status != 'cancelled'` vs `WHERE status IN ('placed', 'shipped', 'delivered')`).
- **Comparing LLM SQL Output against Human-Authored Reference SQL Output**:
  - *Why rejected*: Both rely on the same database engine and schema assumptions, risking shared blind spots.

### Rationale & Trade-offs
- Provides true dual-implementation verification: Python business logic verifies PostgreSQL query engine results.
- Compares semantic data results (tabular values, row counts, column types, aggregations) rather than syntax.
- Allows continuous verification of ground truth even if database schemas undergo migration.

### Student Interview Talking Point
> *"We avoid circular verification by calculating ground truth answers in pure Python directly from our raw seed data. Our evaluation suite compares the tabular data returned by the database against the Python calculation, ensuring true semantic correctness."*

---

## ADR-008: Two Separate Evaluation Tracks: Mock-LLM Pipeline Tests vs. Live-LLM Accuracy Eval

### Status
Accepted

### Context
An automated test suite has two distinct goals that conflict if combined:
1. Fast, deterministic regression testing in CI/CD on every pull request (needs to run in < 15 seconds, offline, $0 cost).
2. Deep model accuracy benchmarking (tests prompt efficacy, hallucination rates, and LLM reasoning against live LLMs, which incurs cost and API latency).

### Decision
Divide evaluation into two distinct, documented tracks:

1. **Track 1: Mock-LLM Pipeline Test Suite (`tests/` & `eval/run_eval_pipeline.py`)**:
   - Uses `MockLLMProvider`.
   - Runs in CI/CD pipeline on every commit.
   - Tests end-to-end FastAPI endpoints, Pydantic schemas, `sqlglot` AST security policies, database roles, timeout handling, and error envelopes.
   - Execution time: < 5 seconds. Cost: $0.
2. **Track 2: Live-LLM Accuracy & Safety Benchmark (`eval/run_eval_live.py`)**:
   - Uses `AnthropicProvider` (or configured live provider).
   - Executed on-demand, nightly, or when updating system prompts/models.
   - Runs 50+ benchmark cases across 14 categories.
   - Reports Syntax Validity Rate, Security Rejection Rate, Execution Rate, and Semantic Accuracy Rate against Python ground truth.

### Alternatives Considered
- **Running live LLM calls in GitHub Actions CI on every commit**:
  - *Why rejected*: Flaky tests due to API rate limits or network issues, slows down CI feedback loops, and incurs ongoing API costs.

### Rationale & Trade-offs
- Provides immediate developer feedback during local development.
- Keeps CI/CD completely free and hermetic.
- Gives a rigorous statistical framework for evaluating prompt engineering updates.

### Student Interview Talking Point
> *"We separate CI/CD pipeline regression tests from model accuracy evaluations. Pipeline tests run hermetically in seconds using our MockProvider, while the live evaluation harness runs on-demand to benchmark model accuracy and prompt stability against 50+ golden test cases."*
