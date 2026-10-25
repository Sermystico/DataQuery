"""Structured logging configuration for DataQuery.

Ensures log outputs are structured, do not leak credentials or raw SQL connection
strings containing passwords, and include context fields when available.
"""

import logging
import re
import sys

# Regex pattern to match and redact database connection passwords in logs
PASSWORD_PATTERN = re.compile(r"://([^:]+):([^@]+)@")


class RedactingFormatter(logging.Formatter):
    """Logging formatter that redacts sensitive credentials from log messages."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        # Redact connection string passwords like postgresql://user:pass@host
        return PASSWORD_PATTERN.sub(r"://\1:**********@", original)


def setup_logging(level: int = logging.INFO) -> None:
    """Initialize structured application logging."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]

    # Silence verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    return logging.getLogger(name)
