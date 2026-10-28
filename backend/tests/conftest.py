"""Global test fixtures for DataQuery test suite."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def ensure_offline_mode(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Ensure automated tests run strictly offline with mock provider unless explicitly marked with @pytest.mark.live."""
    if "live" in request.keywords:
        yield
        return

    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient instance."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
