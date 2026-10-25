"""Integration tests for GET /api/v1/examples endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_examples_count_and_non_empty(client: TestClient) -> None:
    """Verify examples endpoint returns >= 24 non-empty questions across categories."""
    response = client.get("/api/v1/examples")
    assert response.status_code == 200
    data = response.json()

    assert "total_count" in data
    assert "categories" in data
    assert data["total_count"] >= 24
    assert len(data["categories"]) >= 6

    expected_categories = {
        "aggregation",
        "grouping",
        "top_n",
        "date_based",
        "filtering",
        "joins",
    }
    found_categories = {cat["category"] for cat in data["categories"]}
    assert expected_categories.issubset(found_categories)

    question_count = 0
    for cat in data["categories"]:
        assert len(cat["title"]) > 0
        assert len(cat["description"]) > 0
        assert len(cat["examples"]) > 0

        for ex in cat["examples"]:
            assert "title" in ex
            assert len(ex["title"].strip()) > 0
            assert "question" in ex
            assert len(ex["question"].strip()) >= 5
            question_count += 1

    assert question_count == data["total_count"]
    assert question_count >= 24


@pytest.mark.integration
def test_examples_headers(client: TestClient) -> None:
    """Verify tracking headers are returned on /examples."""
    response = client.get("/api/v1/examples")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers
