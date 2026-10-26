"""Unit tests for database engine dependencies and connection failure handling."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import DatabaseUnavailable
from app.db.engines import (
    dispose_engines,
    get_app_conn,
    get_app_session,
    get_readonly_conn,
    get_readonly_session,
)
from app.db.history_repo import record_query_history


@pytest.mark.unit
def test_get_readonly_conn_happy_path() -> None:
    """Verify get_readonly_conn yields a valid connection."""
    generator = get_readonly_conn()
    conn = next(generator)
    assert conn is not None
    try:
        next(generator)
    except StopIteration:
        pass


@pytest.mark.unit
def test_get_readonly_conn_database_unavailable_re_raised() -> None:
    """Verify DatabaseUnavailable is re-raised directly in get_readonly_conn."""
    with patch("app.db.engines.readonly_engine.connect", side_effect=DatabaseUnavailable("DB down")):
        generator = get_readonly_conn()
        with pytest.raises(DatabaseUnavailable, match="DB down"):
            next(generator)


@pytest.mark.unit
def test_get_readonly_conn_exception_wrapped() -> None:
    """Verify generic exceptions are wrapped into DatabaseUnavailable in get_readonly_conn."""
    with patch("app.db.engines.readonly_engine.connect", side_effect=RuntimeError("Socket error")):
        generator = get_readonly_conn()
        with pytest.raises(DatabaseUnavailable, match="Unable to establish connection"):
            next(generator)


@pytest.mark.unit
def test_get_readonly_session_happy_path() -> None:
    """Verify get_readonly_session yields a valid session."""
    generator = get_readonly_session()
    session = next(generator)
    assert session is not None
    try:
        next(generator)
    except StopIteration:
        pass


@pytest.mark.unit
def test_get_readonly_session_database_unavailable_re_raised() -> None:
    """Verify DatabaseUnavailable is re-raised directly in get_readonly_session."""
    with patch("app.db.engines.readonly_session_factory", side_effect=DatabaseUnavailable("Session down")):
        generator = get_readonly_session()
        with pytest.raises(DatabaseUnavailable, match="Session down"):
            next(generator)


@pytest.mark.unit
def test_get_readonly_session_exception_wrapped() -> None:
    """Verify generic exceptions are wrapped into DatabaseUnavailable in get_readonly_session."""
    with patch("app.db.engines.readonly_session_factory", side_effect=RuntimeError("Session error")):
        generator = get_readonly_session()
        with pytest.raises(DatabaseUnavailable, match="Unable to establish session with PostgreSQL engine."):
            next(generator)


@pytest.mark.unit
def test_get_app_conn_happy_path() -> None:
    """Verify get_app_conn yields a valid connection."""
    generator = get_app_conn()
    conn = next(generator)
    assert conn is not None
    try:
        next(generator)
    except StopIteration:
        pass


@pytest.mark.unit
def test_get_app_conn_database_unavailable_re_raised() -> None:
    """Verify DatabaseUnavailable is re-raised directly in get_app_conn."""
    with patch("app.db.engines.app_engine.connect", side_effect=DatabaseUnavailable("App DB down")):
        generator = get_app_conn()
        with pytest.raises(DatabaseUnavailable, match="App DB down"):
            next(generator)


@pytest.mark.unit
def test_get_app_conn_exception_wrapped() -> None:
    """Verify generic exceptions are wrapped into DatabaseUnavailable in get_app_conn."""
    with patch("app.db.engines.app_engine.connect", side_effect=RuntimeError("App socket error")):
        generator = get_app_conn()
        with pytest.raises(DatabaseUnavailable, match="Unable to establish connection to PostgreSQL app engine."):
            next(generator)


@pytest.mark.unit
def test_get_app_session_happy_path() -> None:
    """Verify get_app_session yields a valid session."""
    generator = get_app_session()
    session = next(generator)
    assert session is not None
    try:
        next(generator)
    except StopIteration:
        pass


@pytest.mark.unit
def test_get_app_session_database_unavailable_re_raised() -> None:
    """Verify DatabaseUnavailable is re-raised directly in get_app_session."""
    with patch("app.db.engines.app_session_factory", side_effect=DatabaseUnavailable("App session down")):
        generator = get_app_session()
        with pytest.raises(DatabaseUnavailable, match="App session down"):
            next(generator)


@pytest.mark.unit
def test_get_app_session_exception_wrapped() -> None:
    """Verify generic exceptions are wrapped into DatabaseUnavailable in get_app_session."""
    with patch("app.db.engines.app_session_factory", side_effect=RuntimeError("App session error")):
        generator = get_app_session()
        with pytest.raises(DatabaseUnavailable, match="Unable to establish session with PostgreSQL app engine."):
            next(generator)


@pytest.mark.unit
def test_dispose_engines() -> None:
    """Verify dispose_engines executes dispose on both engines."""
    with patch("app.db.engines.readonly_engine.dispose") as mock_ro_disp, \
         patch("app.db.engines.app_engine.dispose") as mock_app_disp:
        dispose_engines()
        mock_ro_disp.assert_called_once()
        mock_app_disp.assert_called_once()


@pytest.mark.unit
def test_record_query_history_handles_exception_gracefully() -> None:
    """Verify record_query_history returns None and logs error without raising."""
    with patch("app.db.history_repo.app_engine.connect", side_effect=RuntimeError("DB write failure")):
        result = record_query_history(
            request_id="req_fail_123",
            question="What is total revenue?",
            status="success",
            sql="SELECT 1;",
        )
        assert result is None


@pytest.mark.unit
def test_record_query_history_none_row() -> None:
    """Verify record_query_history returns None when execute fetchone returns None."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_conn

    with patch("app.db.history_repo.app_engine.connect", return_value=mock_ctx):
        result = record_query_history(
            request_id="req_none_row",
            question="What is total revenue?",
            status="success",
            sql="SELECT 1;",
        )
        assert result is None

