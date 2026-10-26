"""Integration test for evaluation runner execution and report generation."""

import json
import sys
from pathlib import Path

import pytest

# Add eval directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from run_eval import execute_evaluation, generate_markdown_report  # noqa: E402


@pytest.mark.evaluation
@pytest.mark.integration
def test_evaluation_runner_executes_and_generates_reports(tmp_path: Path) -> None:
    """Verify execute_evaluation executes all cases with 100% pass rate in mock mode."""
    report_data = execute_evaluation(provider_name="mock")
    summary = report_data["summary"]

    assert summary["total_cases"] >= 50
    assert summary["failed_cases"] == 0
    assert summary["pass_rate_percent"] == 100.0
    assert summary["table_counts_preserved"] is True
    assert summary["negative_control"]["status"] == "PASSED"

    # Test JSON and Markdown report generation
    json_path = tmp_path / "test_report.json"
    md_path = tmp_path / "test_report.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    generate_markdown_report(report_data, md_path)

    assert json_path.exists() and json_path.stat().st_size > 0
    assert md_path.exists() and md_path.stat().st_size > 0

    content = md_path.read_text(encoding="utf-8")
    assert "# DataQuery Evaluation Report" in content
    assert "100.0%" in content
    assert "Negative Control Verification" in content
