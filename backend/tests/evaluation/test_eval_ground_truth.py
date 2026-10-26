"""Tests for independent Python ground-truth calculation."""

import sys
from pathlib import Path

import pytest

# Add eval directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from ground_truth import compute_ground_truth  # noqa: E402

from app.llm.golden_queries import GOLDEN_QUERIES  # noqa: E402


@pytest.mark.evaluation
def test_ground_truth_covers_all_golden_queries() -> None:
    """Verify compute_ground_truth covers 100% of canonical golden queries."""
    gt = compute_ground_truth()
    assert len(gt) >= 32

    for gq in GOLDEN_QUERIES:
        assert gq.id in gt, f"Golden query {gq.id} is missing from ground truth calculations!"
        entry = gt[gq.id]
        assert "columns" in entry and len(entry["columns"]) > 0
        assert "rows" in entry
        assert isinstance(entry["rows"], list)


@pytest.mark.evaluation
def test_ground_truth_deterministic() -> None:
    """Verify compute_ground_truth is pure and yields identical output on repeat invocations."""
    gt1 = compute_ground_truth()
    gt2 = compute_ground_truth()
    assert gt1 == gt2
