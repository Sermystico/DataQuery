"""Unit tests for structured logging and sensitive data masking."""

import logging

import pytest

from app.core.logging import RedactingFormatter, get_logger, setup_logging


@pytest.mark.unit
def test_redacting_formatter_masks_connection_passwords() -> None:
    """Verify RedactingFormatter redacts passwords in database URLs."""
    formatter = RedactingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Connecting to postgresql://dq_owner:my_secret_pw@localhost:5432/dataquery",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "my_secret_pw" not in formatted
    assert "postgresql://dq_owner:**********@localhost:5432/dataquery" in formatted


@pytest.mark.unit
def test_setup_logging_when_handlers_empty() -> None:
    """Verify setup_logging adds handler when root logger has no handlers."""
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    try:
        root.handlers = []
        setup_logging(level=logging.DEBUG)
        assert len(root.handlers) == 1
    finally:
        root.handlers = old_handlers


@pytest.mark.unit
def test_setup_logging_when_handlers_exist() -> None:
    """Verify setup_logging replaces handlers when root logger already has handlers."""
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    try:
        root.handlers = [logging.NullHandler()]
        setup_logging(level=logging.INFO)
        assert len(root.handlers) == 1
    finally:
        root.handlers = old_handlers


@pytest.mark.unit
def test_get_logger() -> None:
    """Verify get_logger returns logger instance with specified name."""
    logger = get_logger("app.custom.test")
    assert logger.name == "app.custom.test"
