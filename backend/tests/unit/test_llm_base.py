"""Unit tests for app.llm.base models and protocols."""

import pytest
from pydantic import ValidationError

from app.llm.base import SQLGeneration


@pytest.mark.unit
def test_sql_generation_supported_valid() -> None:
    """Verify supported=True requires valid non-empty sql."""
    gen = SQLGeneration(supported=True, sql="SELECT id, name FROM customers;")
    assert gen.supported is True
    assert gen.sql == "SELECT id, name FROM customers;"
    assert gen.reason is None


@pytest.mark.unit
def test_sql_generation_supported_missing_sql_raises() -> None:
    """Verify supported=True without sql raises ValidationError."""
    with pytest.raises(ValidationError, match="must be provided"):
        SQLGeneration(supported=True, sql=None)

    with pytest.raises(ValidationError, match="must be provided"):
        SQLGeneration(supported=True, sql="   ")


@pytest.mark.unit
def test_sql_generation_unsupported_valid() -> None:
    """Verify supported=False requires non-empty reason."""
    gen = SQLGeneration(supported=False, reason="Question asks for stock predictions.")
    assert gen.supported is False
    assert gen.sql is None
    assert gen.reason == "Question asks for stock predictions."


@pytest.mark.unit
def test_sql_generation_unsupported_missing_reason_raises() -> None:
    """Verify supported=False without reason raises ValidationError."""
    with pytest.raises(ValidationError, match="must be provided"):
        SQLGeneration(supported=False, reason=None)

    with pytest.raises(ValidationError, match="must be provided"):
        SQLGeneration(supported=False, reason="   ")

