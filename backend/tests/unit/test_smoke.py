"""Smoke test to verify test harness and environment."""

import pytest


@pytest.mark.unit
def test_environment_smoke() -> None:
    """Trivial assertion ensuring pytest executes correctly."""
    assert 1 + 1 == 2


@pytest.mark.unit
def test_backend_package_imports() -> None:
    """Verify that backend packages can be imported without errors."""
    import app
    import app.core
    import app.db
    import app.llm
    import app.schemas
    import app.security
    import app.services

    assert app is not None
