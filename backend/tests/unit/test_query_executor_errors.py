"""Unit tests for query_executor.py error branches and exception mapping."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from app.core.errors import AppError, DatabaseUnavailable
from app.security.query_executor import execute_query
from app.security.sql_validator import validate_sql


@pytest.mark.unit
def test_execute_query_connection_refused_maps_to_database_unavailable() -> None:
    """Verify operational connection error raises DatabaseUnavailable."""
    validation = validate_sql("SELECT id FROM orders LIMIT 5")
    assert validation.validated_sql is not None

    with patch(
        "app.security.query_executor.readonly_engine.connect",
        side_effect=OperationalError("connection refused", params=None, orig=Exception("connection refused")),
    ):
        with pytest.raises(DatabaseUnavailable) as exc_info:
            execute_query(validation.validated_sql)
        assert exc_info.value.code == "DATABASE_UNAVAILABLE"


@pytest.mark.unit
def test_execute_query_other_operational_error_maps_to_app_error() -> None:
    """Verify non-timeout, non-connection operational error raises DATABASE_ERROR."""
    validation = validate_sql("SELECT id FROM orders LIMIT 5")
    assert validation.validated_sql is not None

    with patch(
        "app.security.query_executor.readonly_engine.connect",
        side_effect=OperationalError("disk full or hardware failure", params=None, orig=Exception("disk error")),
    ):
        with pytest.raises(AppError) as exc_info:
            execute_query(validation.validated_sql)
        assert exc_info.value.code == "DATABASE_ERROR"
        assert exc_info.value.http_status == 400


@pytest.mark.unit
def test_execute_query_unexpected_generic_exception_maps_to_app_error() -> None:
    """Verify unanticipated generic exception raises DATABASE_ERROR."""
    validation = validate_sql("SELECT id FROM orders LIMIT 5")
    assert validation.validated_sql is not None

    with patch(
        "app.security.query_executor.readonly_engine.connect",
        side_effect=RuntimeError("Unexpected internal python error"),
    ):
        with pytest.raises(AppError) as exc_info:
            execute_query(validation.validated_sql)
        assert exc_info.value.code == "DATABASE_ERROR"
        assert exc_info.value.http_status == 400


@pytest.mark.unit
def test_execute_query_database_unavailable_passthrough() -> None:
    """Verify DatabaseUnavailable is re-raised directly without re-wrapping."""
    validation = validate_sql("SELECT id FROM orders LIMIT 5")
    assert validation.validated_sql is not None

    with patch(
        "app.security.query_executor.readonly_engine.connect",
        side_effect=DatabaseUnavailable("direct db down"),
    ):
        with pytest.raises(DatabaseUnavailable) as exc_info:
            execute_query(validation.validated_sql)
        assert exc_info.value.message == "direct db down"
