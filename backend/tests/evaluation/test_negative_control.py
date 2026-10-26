"""Negative-control test proving an incorrect expected value makes evaluation fail.

Requirement:
Add a negative-control test proving an incorrect expected value makes evaluation fail.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

# Add eval directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from ground_truth import compute_ground_truth  # noqa: E402
from run_eval import compare_results, run_negative_control  # noqa: E402


@pytest.mark.evaluation
def test_negative_control_numeric_mismatch_fails() -> None:
    """Prove that an incorrect numeric expected value causes comparison to fail."""
    gt = compute_ground_truth()
    actual = gt["AGG-01"]  # Real computed total revenue ~1259220.88

    # Deliberately supply an erroneous expected value
    wrong_expected_rows: list[list[Any]] = [[999999999.99]]
    passed, reason = compare_results(
        expected_cols=actual["columns"],
        expected_rows=wrong_expected_rows,
        actual_cols=actual["columns"],
        actual_rows=actual["rows"],
        tolerance=0.01,
    )

    assert passed is False, "Negative control failed: incorrect numeric value was accepted!"
    assert "Numeric mismatch" in reason
    assert "999999999.99" in reason


@pytest.mark.evaluation
def test_negative_control_column_mismatch_fails() -> None:
    """Prove that a mismatched column name causes comparison to fail."""
    gt = compute_ground_truth()
    actual = gt["AGG-01"]

    wrong_columns = ["wrong_column_name"]
    passed, reason = compare_results(
        expected_cols=wrong_columns,
        expected_rows=actual["rows"],
        actual_cols=actual["columns"],
        actual_rows=actual["rows"],
    )

    assert passed is False, "Negative control failed: mismatched column name was accepted!"
    assert "Column mismatch" in reason


@pytest.mark.evaluation
def test_negative_control_row_count_mismatch_fails() -> None:
    """Prove that an extra or missing row causes comparison to fail."""
    gt = compute_ground_truth()
    actual = gt["AGG-01"]

    # Supply an extra row
    extra_rows = actual["rows"] + [[500.0]]
    passed, reason = compare_results(
        expected_cols=actual["columns"],
        expected_rows=extra_rows,
        actual_cols=actual["columns"],
        actual_rows=actual["rows"],
    )

    assert passed is False, "Negative control failed: incorrect row count was accepted!"
    assert "Row count mismatch" in reason


@pytest.mark.evaluation
def test_run_negative_control_suite_passes() -> None:
    """Prove that the overall negative control suite executes and passes all rejection tests."""
    gt = compute_ground_truth()
    res = run_negative_control(gt)
    assert res["status"] == "PASSED"
    assert len(res["tested_scenarios"]) == 3
