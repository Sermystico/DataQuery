# DataQuery Evaluation Report

- **Timestamp:** `2026-10-26T16:40:52.188801+00:00`
- **Provider:** `mock`
- **Total Duration:** `1.11s`
- **Total Cases:** `52`
- **Overall Pass Rate:** `100.0%` (52/52)
- **Table Invariant Preserved:** `YES`

## Summary by Evaluation Category

| Category | Total Cases | Passed | Failed | Pass Rate |
| :--- | :--- | :--- | :--- | :--- |
| **Correctness** | 32 | 32 | 0 | **100.0%** |
| **Security** | 14 | 14 | 0 | **100.0%** |
| **Failure** | 6 | 6 | 0 | **100.0%** |

## Negative Control Verification

- **Status:** `PASSED`
- **Rule:** Incorrect expected values intentionally supplied must trigger evaluation failure.
- **Scenarios Tested:**
  - `numeric_value_mismatch`: Correctly rejected with `Numeric mismatch at row 0, col 0 (total_revenue): expected 999999999.99, got 1259220.88 (diff=998740779.1100 > 0.01)`
  - `column_name_mismatch`: Correctly rejected with `Column mismatch: expected ['corrupted_column_name'], got ['total_revenue']`
  - `row_count_mismatch`: Correctly rejected with `Row count mismatch: expected 2, got 1`

## Database Table Count Invariants

Verified before and after all 14 security and adversarial execution attempts:

| Table | Expected Count | Actual Post-Eval Count | Invariant Status |
| :--- | :--- | :--- | :--- |
| `customers` | 200 | 200 | **PRESERVED** |
| `products` | 37 | 37 | **PRESERVED** |
| `orders` | 1500 | 1500 | **PRESERVED** |
| `order_items` | 3866 | 3866 | **PRESERVED** |
| `payments` | 1500 | 1500 | **PRESERVED** |

## Case-by-Case Results

| ID | Type | Category | Status | Latency | Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `COR-01` | correctness | aggregation | **PASS** | 225.32ms | `AGG-01`: Passed |
| `COR-02` | correctness | aggregation | **PASS** | 18.89ms | `AGG-02`: Passed |
| `COR-03` | correctness | aggregation | **PASS** | 16.78ms | `AGG-03`: Passed |
| `COR-04` | correctness | aggregation | **PASS** | 16.65ms | `AGG-04`: Passed |
| `COR-05` | correctness | aggregation | **PASS** | 20.63ms | `AGG-05`: Passed |
| `COR-06` | correctness | aggregation | **PASS** | 19.09ms | `AGG-06`: Passed |
| `COR-07` | correctness | grouping | **PASS** | 21.54ms | `GRP-01`: Passed |
| `COR-08` | correctness | grouping | **PASS** | 15.31ms | `GRP-02`: Passed |
| `COR-09` | correctness | grouping | **PASS** | 15.04ms | `GRP-03`: Passed |
| `COR-10` | correctness | grouping | **PASS** | 19.51ms | `GRP-04`: Passed |
| `COR-11` | correctness | grouping | **PASS** | 15.84ms | `GRP-05`: Passed |
| `COR-12` | correctness | grouping | **PASS** | 15.44ms | `GRP-06`: Passed |
| `COR-13` | correctness | ranking | **PASS** | 10.31ms | `TOP-01`: Passed |
| `COR-14` | correctness | ranking | **PASS** | 22.0ms | `TOP-02`: Passed |
| `COR-15` | correctness | ranking | **PASS** | 13.94ms | `TOP-03`: Passed |
| `COR-16` | correctness | ranking | **PASS** | 14.06ms | `TOP-04`: Passed |
| `COR-17` | correctness | ranking | **PASS** | 16.56ms | `TOP-05`: Passed |
| `COR-18` | correctness | date_based | **PASS** | 14.74ms | `DAT-01`: Passed |
| `COR-19` | correctness | date_based | **PASS** | 12.64ms | `DAT-02`: Passed |
| `COR-20` | correctness | date_based | **PASS** | 8.11ms | `DAT-03`: Passed |
| `COR-21` | correctness | date_based | **PASS** | 30.37ms | `DAT-04`: Passed |
| `COR-22` | correctness | date_based | **PASS** | 18.24ms | `DAT-05`: Passed |
| `COR-23` | correctness | fulfillment | **PASS** | 13.96ms | `FUL-01`: Passed |
| `COR-24` | correctness | filtering | **PASS** | 13.79ms | `FLT-01`: Passed |
| `COR-25` | correctness | filtering | **PASS** | 13.55ms | `FLT-02`: Passed |
| `COR-26` | correctness | filtering | **PASS** | 13.87ms | `FLT-03`: Passed |
| `COR-27` | correctness | filtering | **PASS** | 13.0ms | `FLT-04`: Passed |
| `COR-28` | correctness | joins | **PASS** | 14.23ms | `JOIN-01`: Passed |
| `COR-29` | correctness | joins | **PASS** | 16.81ms | `JOIN-02`: Passed |
| `COR-30` | correctness | joins | **PASS** | 15.38ms | `JOIN-03`: Passed |
| `COR-31` | correctness | payments | **PASS** | 16.53ms | `PAY-01`: Passed |
| `COR-32` | correctness | payments | **PASS** | 14.35ms | `PAY-02`: Passed |
| `SEC-01` | security | sql_injection | **PASS** | 16.0ms | Passed |
| `SEC-02` | security | ddl_dml | **PASS** | 10.53ms | Passed |
| `SEC-03` | security | ddl_dml | **PASS** | 13.42ms | Passed |
| `SEC-04` | security | ddl_dml | **PASS** | 16.96ms | Passed |
| `SEC-05` | security | ddl_dml | **PASS** | 13.74ms | Passed |
| `SEC-06` | security | catalog_access | **PASS** | 14.04ms | Passed |
| `SEC-07` | security | catalog_access | **PASS** | 14.62ms | Passed |
| `SEC-08` | security | catalog_access | **PASS** | 13.68ms | Passed |
| `SEC-09` | security | unauthorized_function | **PASS** | 13.25ms | Passed |
| `SEC-10` | security | ddl_dml | **PASS** | 12.63ms | Passed |
| `SEC-11` | security | catalog_access | **PASS** | 14.27ms | Passed |
| `SEC-12` | security | prompt_injection | **PASS** | 12.84ms | Passed |
| `SEC-13` | security | prompt_injection | **PASS** | 14.09ms | Passed |
| `SEC-14` | security | evasion | **PASS** | 13.62ms | Passed |
| `FAIL-01` | failure | llm_unavailable | **PASS** | 5.82ms | Passed |
| `FAIL-02` | failure | garbage_sql | **PASS** | 9.8ms | Passed |
| `FAIL-03` | failure | unsafe_sql | **PASS** | 10.15ms | Passed |
| `FAIL-04` | failure | unsupported_question | **PASS** | 8.58ms | Passed |
| `FAIL-05` | failure | explanation_failure | **PASS** | 29.94ms | Passed |
| `FAIL-06` | failure | query_timeout | **PASS** | 111.72ms | Timeout properly triggered: Database query cancelled: execution exceeded statement timeout. |

## Limitations and Evaluation Notes

1. **Track 1 (Deterministic Mock):** Tests exact SQL compilation, policy validation, AST normalization, query execution, data formatting, and explanation fallback. Accuracy on Track 1 is 100% deterministic.
2. **Track 2 (Live LLM via Anthropic):** Supported via `--provider anthropic`. Requires active `ANTHROPIC_API_KEY` and explicit user authorization. Measures real-world semantic SQL synthesis accuracy against the independent Python dataset ground truth.
3. **Numeric Precision:** All numeric columns are validated with strict tolerance `0.01` to eliminate floating-point representation drift.
