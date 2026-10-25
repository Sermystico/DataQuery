"""Global test fixtures for DataQuery test suite."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient instance."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
