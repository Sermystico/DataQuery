"""Core configuration, constants, logging, and error handling package."""

from app.core.config import Settings, get_settings
from app.core.errors import (
    AppError,
    DatabaseUnavailable,
    FeatureNotImplemented,
    InternalError,
    LLMUnavailable,
    NotFound,
    QueryTimeout,
    UnsupportedQuestion,
    ValidationRejected,
    register_error_handlers,
)
from app.core.logging import get_logger, setup_logging

__all__ = [
    "AppError",
    "DatabaseUnavailable",
    "FeatureNotImplemented",
    "InternalError",
    "LLMUnavailable",
    "NotFound",
    "QueryTimeout",
    "Settings",
    "UnsupportedQuestion",
    "ValidationRejected",
    "get_logger",
    "get_settings",
    "register_error_handlers",
    "setup_logging",
]
