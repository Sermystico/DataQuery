"""DataQuery Automated Evaluation Engine (Phase 8).

Executes comprehensive evaluation across:
1. 32 Correctness Cases (Ground truth independently computed in Python via seed dataset).
2. 14 Security & Adversarial Cases (SQL validation, permission invariants, prompt injection).
3. 6 Failure & Resilience Cases (LLM unavailable, garbage SQL, timeouts, explanation failure).

Features:
- Track 1: Deterministic mock evaluation (--provider mock).
- Track 2: Live LLM accuracy evaluation (--provider anthropic).
- Negative-control verification ensuring intentional corruption is detected.
- Independent table count invariant verification before and after execution.
- Generates eval/reports/latest.json and eval/reports/latest.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import yaml
from starlette.testclient import TestClient

# Ensure project root and backend are on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
EVAL_DIR = PROJECT_ROOT / "eval"

for path in [str(PROJECT_ROOT), str(BACKEND_DIR), str(EVAL_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app.api.v1.query import get_llm_provider
from app.core.config import get_settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.mock_provider import MockLLMProvider
from app.main import app
from ground_truth import compute_ground_truth

EXPECTED_TABLE_COUNTS = {
    "customers": 200,
    "products": 37,
    "orders": 1500,
    "order_items": 3866,
    "payments": 1500,
}


def compare_results(
    expected_cols: list[str],
    expected_rows: list[list[Any]],
    actual_cols: list[str],
    actual_rows: list[list[Any]],
    tolerance: float = 0.01,
) -> tuple[bool, str]:
    """Compare actual query execution results against independent Python ground truth."""
    # 1. Compare columns (case-insensitive)
    if [c.lower() for c in expected_cols] != [c.lower() for c in actual_cols]:
        return False, f"Column mismatch: expected {expected_cols}, got {actual_cols}"

    # 2. Compare row count
    if len(expected_rows) != len(actual_rows):
        return (
            False,
            f"Row count mismatch: expected {len(expected_rows)}, got {len(actual_rows)}",
        )

    # 3. Compare values row by row
    for r_idx, (exp_row, act_row) in enumerate(zip(expected_rows, actual_rows, strict=True)):
        for c_idx, (exp_val, act_val) in enumerate(zip(exp_row, act_row, strict=True)):
            col_name = expected_cols[c_idx]

            # Normalize ISO datetime / date strings (handle tz offsets like +00:00 or Z)
            if isinstance(exp_val, str) and isinstance(act_val, str):
                exp_clean = exp_val.replace("+00:00", "").replace("Z", "").strip()
                act_clean = act_val.replace("+00:00", "").replace("Z", "").strip()
                if exp_clean != act_clean:
                    return (
                        False,
                        f"Value mismatch at row {r_idx}, col {c_idx} ({col_name}): "
                        f"expected {exp_val!r}, got {act_val!r}",
                    )
            # Numeric comparison with specified tolerance
            elif isinstance(exp_val, (int, float, Decimal)) and isinstance(
                act_val, (int, float, Decimal)
            ):
                exp_num = float(exp_val)
                act_num = float(act_val)
                if abs(exp_num - act_num) > tolerance:
                    return (
                        False,
                        f"Numeric mismatch at row {r_idx}, col {c_idx} ({col_name}): "
                        f"expected {exp_num}, got {act_num} (diff={abs(exp_num - act_num):.4f} > {tolerance})",
                    )
            else:
                if str(exp_val) != str(act_val):
                    return (
                        False,
                        f"Value mismatch at row {r_idx}, col {c_idx} ({col_name}): "
                        f"expected {exp_val!r}, got {act_val!r}",
                    )

    return True, "Passed"


def get_table_counts() -> dict[str, int]:
    """Retrieve actual row counts for all 5 analytics tables using owner connection."""
    settings = get_settings()
    conn = psycopg.connect(
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_OWNER_USER,
        password=settings.POSTGRES_OWNER_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
    )
    counts = {}
    with conn.cursor() as cur:
        for table in EXPECTED_TABLE_COUNTS:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            counts[table] = cur.fetchone()[0]
    conn.close()
    return counts


def run_negative_control(ground_truth: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Verify that intentional corruption in expected values causes compare_results to fail.

    Tests:
    1. Incorrect numeric value (e.g. wrong revenue).
    2. Incorrect column name.
    3. Incorrect row count.
    """
    sample = ground_truth.get("AGG-01")
    if not sample:
        raise ValueError("Cannot run negative control: AGG-01 missing from ground truth.")

    actual_cols = sample["columns"]
    actual_rows = sample["rows"]

    # Test 1: Value corruption
    corrupted_rows = [[999999999.99]]
    val_passed, val_reason = compare_results(
        sample["columns"], corrupted_rows, actual_cols, actual_rows
    )
    if val_passed:
        raise AssertionError("Negative control failed: corrupted numeric value was accepted!")

    # Test 2: Column name corruption
    corrupted_cols = ["corrupted_column_name"]
    col_passed, col_reason = compare_results(
        corrupted_cols, sample["rows"], actual_cols, actual_rows
    )
    if col_passed:
        raise AssertionError("Negative control failed: corrupted column name was accepted!")

    # Test 3: Row count corruption
    corrupted_count_rows = sample["rows"] + [[123.45]]
    cnt_passed, cnt_reason = compare_results(
        sample["columns"], corrupted_count_rows, actual_cols, actual_rows
    )
    if cnt_passed:
        raise AssertionError("Negative control failed: corrupted row count was accepted!")

    return {
        "status": "PASSED",
        "tested_scenarios": [
            {"type": "numeric_value_mismatch", "detected_reason": val_reason},
            {"type": "column_name_mismatch", "detected_reason": col_reason},
            {"type": "row_count_mismatch", "detected_reason": cnt_reason},
        ],
    }


def execute_evaluation(
    provider_name: str = "mock",
    cases_path: Path | None = None,
    delay_seconds: float = 0.0,
) -> dict[str, Any]:
    """Execute complete evaluation suite against DataQuery API."""
    cases_file = cases_path or (EVAL_DIR / "cases.yaml")
    if not cases_file.exists():
        raise FileNotFoundError(f"Cases configuration file not found at {cases_file}")

    with open(cases_file, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cases = config.get("cases", [])
    settings = get_settings()

    # Configure provider
    if provider_name == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY.get_secret_value() if settings.ANTHROPIC_API_KEY else ""
        if not api_key:
            raise ValueError(
                "Cannot run live evaluation: ANTHROPIC_API_KEY is not configured in settings."
            )
        live_provider = AnthropicProvider(api_key=api_key)
        app.dependency_overrides[get_llm_provider] = lambda: live_provider
    elif provider_name == "gemini":
        api_key = settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else ""
        if not api_key:
            raise ValueError(
                "Cannot run live evaluation: GEMINI_API_KEY is not configured in settings."
            )
        if not settings.GEMINI_MODEL:
            raise ValueError(
                "Cannot run live evaluation: GEMINI_MODEL is not configured in settings."
            )
        from app.llm.gemini_provider import GeminiProvider

        live_provider = GeminiProvider(api_key=api_key, model=settings.GEMINI_MODEL)
        app.dependency_overrides[get_llm_provider] = lambda: live_provider
    else:
        # Default mock provider
        app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="normal")

    client = TestClient(app)

    # 1. Compute ground truth purely in Python
    ground_truth = compute_ground_truth()

    # 2. Run negative control verification
    negative_control_res = run_negative_control(ground_truth)

    # 3. Check initial table count invariant
    initial_counts = get_table_counts()
    for tbl, expected in EXPECTED_TABLE_COUNTS.items():
        if initial_counts[tbl] != expected:
            raise RuntimeError(
                f"Initial table count for '{tbl}' is {initial_counts[tbl]}, expected {expected}."
            )

    results: list[dict[str, Any]] = []
    start_time = time.time()

    for case in cases:
        case_id = case["id"]
        case_type = case["type"]
        category = case.get("category", "general")
        case_start = time.time()

        # ---------------------------------------------------------------------
        # Correctness Case
        # ---------------------------------------------------------------------
        if case_type == "correctness":
            canonical_id = case["canonical_id"]
            question = case["question"]
            expected = ground_truth.get(canonical_id)

            resp = client.post("/api/v1/query", json={"question": question})
            duration_ms = round((time.time() - case_start) * 1000, 2)

            if resp.status_code != 200:
                results.append(
                    {
                        "id": case_id,
                        "type": case_type,
                        "category": category,
                        "question": question,
                        "passed": False,
                        "status_code": resp.status_code,
                        "duration_ms": duration_ms,
                        "reason": f"Expected HTTP 200, got {resp.status_code}: {resp.text}",
                    }
                )
                continue

            data = resp.json()
            if data.get("status") != "success":
                results.append(
                    {
                        "id": case_id,
                        "type": case_type,
                        "category": category,
                        "question": question,
                        "passed": False,
                        "status_code": resp.status_code,
                        "duration_ms": duration_ms,
                        "reason": f"Query status was {data.get('status')}: {data.get('rejection_reasons')}",
                    }
                )
                continue

            passed, reason = compare_results(
                expected["columns"],
                expected["rows"],
                data.get("columns", []),
                data.get("rows", []),
            )

            results.append(
                {
                    "id": case_id,
                    "type": case_type,
                    "category": category,
                    "canonical_id": canonical_id,
                    "question": question,
                    "passed": passed,
                    "status_code": resp.status_code,
                    "duration_ms": duration_ms,
                    "generated_sql": data.get("sql"),
                    "row_count": data.get("row_count"),
                    "reason": reason,
                }
            )

        # ---------------------------------------------------------------------
        # Security Case
        # ---------------------------------------------------------------------
        elif case_type == "security":
            malicious_sql = case["sql"]
            question = case["question"]

            # Test 1: Validate endpoint rejects SQL
            val_resp = client.post("/api/v1/sql/validate", json={"sql": malicious_sql})
            val_data = val_resp.json()
            sql_rejected = (val_resp.status_code == 200) and (val_data.get("valid") is False)

            # Test 2: Query endpoint blocks prompt injection or adversarial input
            query_resp = client.post("/api/v1/query", json={"question": question})
            query_data = query_resp.json()
            query_blocked = (
                (query_resp.status_code == 400)
                or (
                    query_resp.status_code == 200
                    and query_data.get("status") in ("unsupported", "rejected")
                )
            )

            duration_ms = round((time.time() - case_start) * 1000, 2)
            passed = sql_rejected and query_blocked
            reason = "Passed" if passed else f"Rejection failed: sql_rejected={sql_rejected}, query_blocked={query_blocked}"

            results.append(
                {
                    "id": case_id,
                    "type": case_type,
                    "category": category,
                    "description": case.get("description"),
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "sql_rejection": sql_rejected,
                    "query_blocked": query_blocked,
                    "reasons": val_data.get("reasons", []),
                    "reason": reason,
                }
            )

        # ---------------------------------------------------------------------
        # Failure & Resilience Case
        # ---------------------------------------------------------------------
        elif case_type == "failure":
            failure_mode = case["failure_mode"]
            expected_status = case["expected_status"]
            expected_error_code = case.get("expected_error_code")
            question = case["question"]

            if failure_mode == "timeout":
                # Legal cross-join query with statement timeout configured to 100ms
                heavy_sql = (
                    "SELECT count(*) FROM order_items oi1 "
                    "CROSS JOIN order_items oi2 "
                    "CROSS JOIN order_items oi3 "
                    "CROSS JOIN order_items oi4;"
                )
                from app.security.query_executor import execute_query
                from app.security.sql_validator import validate_sql

                validation = validate_sql(heavy_sql)
                orig_timeout = settings.QUERY_TIMEOUT_MS
                settings.QUERY_TIMEOUT_MS = 100
                try:
                    execute_query(validation.validated_sql)
                    passed = False
                    reason = "Heavy query did not time out as expected"
                except Exception as ex:
                    passed = "statement timeout" in str(ex).lower() or "57014" in str(ex) or "canceling statement due to statement timeout" in str(ex).lower()
                    reason = f"Timeout properly triggered: {ex}" if passed else str(ex)
                finally:
                    settings.QUERY_TIMEOUT_MS = orig_timeout

                duration_ms = round((time.time() - case_start) * 1000, 2)
                results.append(
                    {
                        "id": case_id,
                        "type": case_type,
                        "category": category,
                        "description": case.get("description"),
                        "passed": passed,
                        "duration_ms": duration_ms,
                        "reason": reason,
                    }
                )
            else:
                # Override provider mode
                if failure_mode == "raise":
                    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="raise")
                elif failure_mode == "garbage":
                    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="garbage")
                elif failure_mode == "unsafe_sql":
                    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="unsafe_sql")
                elif failure_mode == "unsupported":
                    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="unsupported")
                elif failure_mode == "raise_explain":
                    app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(explain_fail=True)

                resp = client.post("/api/v1/query", json={"question": question})
                duration_ms = round((time.time() - case_start) * 1000, 2)
                status_ok = resp.status_code == expected_status

                data = resp.json()
                if failure_mode in ("garbage", "unsafe_sql"):
                    status_val = case.get("expected_query_status", "rejected")
                    passed = status_ok and (data.get("status") == status_val) and len(data.get("rejection_reasons", [])) > 0
                    reason = "Passed" if passed else f"Expected status={status_val}, got {data.get('status')}"
                elif failure_mode == "unsupported":
                    passed = status_ok and (data.get("status") == "unsupported")
                    reason = "Passed" if passed else f"Expected status=unsupported, got {data.get('status')}"
                elif failure_mode == "raise_explain":
                    expected_src = case.get("expected_explanation_source", "fallback")
                    passed = status_ok and (data.get("status") == "success") and (data.get("explanation_source") == expected_src)
                    reason = "Passed" if passed else f"Expected explanation_source={expected_src}, got {data.get('explanation_source')}"
                else:
                    error_envelope = data.get("error", {})
                    code_match = error_envelope.get("code") == expected_error_code
                    passed = status_ok and code_match
                    reason = "Passed" if passed else f"Expected {expected_status} / {expected_error_code}, got {resp.status_code} / {error_envelope.get('code')}"

                results.append(
                    {
                        "id": case_id,
                        "type": case_type,
                        "category": category,
                        "description": case.get("description"),
                        "passed": passed,
                        "status_code": resp.status_code,
                        "duration_ms": duration_ms,
                        "reason": reason,
                    }
                )

                # Reset provider override
                app.dependency_overrides[get_llm_provider] = lambda: MockLLMProvider(mode="normal")

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    # 4. Verify table counts remained completely unchanged
    final_counts = get_table_counts()
    table_counts_preserved = (initial_counts == final_counts)

    total_duration_sec = round(time.time() - start_time, 2)
    total_cases = len(results)
    passed_cases = sum(1 for r in results if r["passed"])
    failed_cases = total_cases - passed_cases
    pass_rate = round((passed_cases / total_cases) * 100, 2) if total_cases > 0 else 0.0

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "provider": provider_name,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate_percent": pass_rate,
        "duration_seconds": total_duration_sec,
        "table_counts_preserved": table_counts_preserved,
        "table_counts": final_counts,
        "negative_control": negative_control_res,
        "breakdown": {
            "correctness": {
                "total": sum(1 for r in results if r["type"] == "correctness"),
                "passed": sum(1 for r in results if r["type"] == "correctness" and r["passed"]),
            },
            "security": {
                "total": sum(1 for r in results if r["type"] == "security"),
                "passed": sum(1 for r in results if r["type"] == "security" and r["passed"]),
            },
            "failure": {
                "total": sum(1 for r in results if r["type"] == "failure"),
                "passed": sum(1 for r in results if r["type"] == "failure" and r["passed"]),
            },
        },
    }

    return {"summary": summary, "results": results}


def generate_markdown_report(report_data: dict[str, Any], output_path: Path) -> None:
    """Generate comprehensive GitHub-flavored Markdown evaluation report."""
    summary = report_data["summary"]
    results = report_data["results"]

    lines: list[str] = [
        "# DataQuery Evaluation Report",
        "",
        f"- **Timestamp:** `{summary['timestamp']}`",
        f"- **Provider:** `{summary['provider']}`",
        f"- **Total Duration:** `{summary['duration_seconds']}s`",
        f"- **Total Cases:** `{summary['total_cases']}`",
        f"- **Overall Pass Rate:** `{summary['pass_rate_percent']}%` ({summary['passed_cases']}/{summary['total_cases']})",
        f"- **Table Invariant Preserved:** `{'YES' if summary['table_counts_preserved'] else 'NO'}`",
        "",
        "## Summary by Evaluation Category",
        "",
        "| Category | Total Cases | Passed | Failed | Pass Rate |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for cat_name, cat_stats in summary["breakdown"].items():
        total = cat_stats["total"]
        passed = cat_stats["passed"]
        failed = total - passed
        rate = round((passed / total) * 100, 1) if total > 0 else 0.0
        lines.append(f"| **{cat_name.title()}** | {total} | {passed} | {failed} | **{rate}%** |")

    lines.extend([
        "",
        "## Negative Control Verification",
        "",
        "- **Status:** `PASSED`",
        "- **Rule:** Incorrect expected values intentionally supplied must trigger evaluation failure.",
        "- **Scenarios Tested:**",
    ])
    for sc in summary["negative_control"]["tested_scenarios"]:
        lines.append(f"  - `{sc['type']}`: Correctly rejected with `{sc['detected_reason']}`")

    lines.extend([
        "",
        "## Database Table Count Invariants",
        "",
        "Verified before and after all 14 security and adversarial execution attempts:",
        "",
        "| Table | Expected Count | Actual Post-Eval Count | Invariant Status |",
        "| :--- | :--- | :--- | :--- |",
    ])
    for tbl, cnt in summary["table_counts"].items():
        exp = EXPECTED_TABLE_COUNTS[tbl]
        match = "PRESERVED" if cnt == exp else "VIOLATED"
        lines.append(f"| `{tbl}` | {exp} | {cnt} | **{match}** |")

    lines.extend([
        "",
        "## Case-by-Case Results",
        "",
        "| ID | Type | Category | Status | Latency | Details |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ])
    for r in results:
        status_badge = "PASS" if r["passed"] else "FAIL"
        cid = r["id"]
        ctype = r["type"]
        cat = r.get("category", "")
        latency = f"{r.get('duration_ms', 0)}ms"
        details = r.get("reason", "")
        if r.get("canonical_id"):
            details = f"`{r['canonical_id']}`: {details}"
        lines.append(f"| `{cid}` | {ctype} | {cat} | **{status_badge}** | {latency} | {details} |")

    lines.extend([
        "",
        "## Limitations and Evaluation Notes",
        "",
        "1. **Track 1 (Deterministic Mock):** Tests exact SQL compilation, policy validation, AST normalization, query execution, data formatting, and explanation fallback. Accuracy on Track 1 is 100% deterministic.",
        "2. **Track 2 (Live LLM via Anthropic):** Supported via `--provider anthropic`. Requires active `ANTHROPIC_API_KEY` and explicit user authorization. Measures real-world semantic SQL synthesis accuracy against the independent Python dataset ground truth.",
        "3. **Numeric Precision:** All numeric columns are validated with strict tolerance `0.01` to eliminate floating-point representation drift.",
        "",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    """CLI entrypoint for DataQuery evaluation runner."""
    parser = argparse.ArgumentParser(description="DataQuery Evaluation Runner (Phase 8)")
    parser.add_argument(
        "--provider",
        choices=["mock", "anthropic", "gemini"],
        default="mock",
        help="LLM provider for evaluation (default: mock)",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.0,
        help="Optional delay in seconds between evaluation cases for live runs (default: 0)",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=EVAL_DIR / "cases.yaml",
        help="Path to evaluation test cases YAML",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=EVAL_DIR / "reports" / "latest.json",
        help="Path to output JSON evaluation report",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=EVAL_DIR / "reports" / "latest.md",
        help="Path to output Markdown evaluation report",
    )
    parser.add_argument(
        "--negative-control-only",
        action="store_true",
        help="Run only the negative-control test",
    )

    args = parser.parse_args()

    if args.negative_control_only:
        gt = compute_ground_truth()
        res = run_negative_control(gt)
        print(f"Negative control result: {res}")
        return 0

    print(f"Starting DataQuery evaluation with provider='{args.provider}'...")
    report_data = execute_evaluation(
        provider_name=args.provider,
        cases_path=args.cases,
        delay_seconds=args.delay_seconds,
    )

    summary = report_data["summary"]
    print(
        f"Evaluation finished: {summary['passed_cases']}/{summary['total_cases']} passed "
        f"({summary['pass_rate_percent']}%) in {summary['duration_seconds']}s"
    )

    # Write JSON report
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Wrote JSON report to {args.output_json}")

    # Write Markdown report
    generate_markdown_report(report_data, args.output_md)
    print(f"Wrote Markdown report to {args.output_md}")

    if summary["failed_cases"] > 0:
        print(f"WARNING: {summary['failed_cases']} evaluation cases failed!")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
