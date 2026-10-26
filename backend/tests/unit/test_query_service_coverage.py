"""Unit tests for query_service error recording and provider defaults."""

from unittest.mock import patch

import pytest

from app.core.errors import QueryTimeout
from app.services.query_service import run_query


@pytest.mark.unit
def test_run_query_default_provider_resolution() -> None:
    """Verify run_query resolves provider when provider is None."""
    resp = run_query(
        question="What is the total revenue across all completed orders?",
        request_id="req_def_prov",
        provider=None,
    )
    assert resp.status == "success"
    assert resp.answer is not None


@pytest.mark.unit
def test_run_query_handles_app_error_in_execution_and_records_history() -> None:
    """Verify AppError in execution step records history with error status and re-raises."""
    with patch(
        "app.services.query_service._execute_query_step",
        side_effect=QueryTimeout("Statement execution timed out."),
    ), patch("app.services.query_service.record_query_history") as mock_record:
        with pytest.raises(QueryTimeout):
            run_query(
                question="What is the total revenue across all completed orders?",
                request_id="req_app_err_hist",
            )
        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        assert kwargs["status"] == "error"
        assert kwargs["error_code"] == "QUERY_TIMEOUT"


@pytest.mark.unit
def test_run_query_handles_generic_exception_in_execution_and_records_history() -> None:
    """Verify generic exception in execution step records history with INTERNAL_ERROR and re-raises."""
    with patch(
        "app.services.query_service._execute_query_step",
        side_effect=RuntimeError("Unexpected OS crash"),
    ), patch("app.services.query_service.record_query_history") as mock_record:
        with pytest.raises(RuntimeError):
            run_query(
                question="What is the total revenue across all completed orders?",
                request_id="req_gen_err_hist",
            )
        mock_record.assert_called_once()
        kwargs = mock_record.call_args[1]
        assert kwargs["status"] == "error"
        assert kwargs["error_code"] == "INTERNAL_ERROR"
