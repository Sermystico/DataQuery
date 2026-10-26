"""Unit tests for OllamaProvider: connection handling, parsing, fallbacks, and security."""

import os
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import LLMUnavailable
from app.llm.base import SQLGeneration
from app.llm.ollama_provider import OllamaProvider
from app.services.query_service import run_query


def _create_mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str = "",
) -> httpx.Response:
    """Helper to create realistic httpx.Response instances."""
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    if json_data is not None:
        return httpx.Response(status_code=status_code, json=json_data, request=request)
    return httpx.Response(status_code=status_code, text=text, request=request)


@pytest.mark.unit
def test_ollama_provider_defaults_and_initialization() -> None:
    """Verify OllamaProvider initializes with proper defaults and cleans base_url."""
    provider = OllamaProvider(
        base_url="http://localhost:11434/",
        model="llama3.2:latest",
        timeout=45.0,
    )
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "llama3.2:latest"
    assert provider.timeout == 45.0
    assert provider.client is not None


@pytest.mark.unit
def test_ollama_generate_sql_success() -> None:
    """Verify successful parsing of structured JSON generation from Ollama."""
    mock_client = MagicMock()
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={
            "message": {
                "content": '{"supported": true, "sql": "SELECT COUNT(*) FROM orders;"}'
            }
        },
    )

    provider = OllamaProvider(client=mock_client)
    res = provider.generate_sql("How many orders exist?")

    assert isinstance(res, SQLGeneration)
    assert res.supported is True
    assert res.sql == "SELECT COUNT(*) FROM orders;"
    assert res.reason is None


@pytest.mark.unit
def test_ollama_generate_sql_markdown_fence_stripped() -> None:
    """Verify markdown code block wrappers are stripped before schema validation."""
    mock_client = MagicMock()
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={
            "message": {
                "content": '```json\n{"supported": true, "sql": "SELECT id FROM products;"}\n```'
            }
        },
    )

    provider = OllamaProvider(client=mock_client)
    res = provider.generate_sql("List product IDs")

    assert res.supported is True
    assert res.sql == "SELECT id FROM products;"


@pytest.mark.unit
def test_ollama_generate_sql_unsupported_question() -> None:
    """Verify unsupported questions with reason are cleanly parsed."""
    mock_client = MagicMock()
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={
            "message": {
                "content": '{"supported": false, "reason": "Weather data is not available."}'
            }
        },
    )

    provider = OllamaProvider(client=mock_client)
    res = provider.generate_sql("What is the weather in Paris?")

    assert res.supported is False
    assert res.sql is None
    assert res.reason == "Weather data is not available."


@pytest.mark.unit
def test_ollama_generate_sql_missing_content() -> None:
    """Verify empty or missing message content raises LLMUnavailable."""
    mock_client = MagicMock()
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={"message": {"content": "   "}},
    )

    provider = OllamaProvider(client=mock_client)
    with pytest.raises(LLMUnavailable, match="invalid response structure"):
        provider.generate_sql("Test query")


@pytest.mark.unit
def test_ollama_generate_sql_malformed_json() -> None:
    """Verify invalid JSON syntax or schema mismatch raises LLMUnavailable."""
    mock_client = MagicMock()
    # Malformed JSON
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={"message": {"content": "{not valid json}"}},
    )

    provider = OllamaProvider(client=mock_client)
    with pytest.raises(LLMUnavailable, match="malformed structured data"):
        provider.generate_sql("Test query")

    # Schema violation: supported=True but missing sql
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={"message": {"content": '{"supported": true}'}},
    )
    with pytest.raises(LLMUnavailable, match="malformed structured data"):
        provider.generate_sql("Test query")


@pytest.mark.unit
def test_ollama_generate_sql_connection_error() -> None:
    """Verify connection failure raises LLMUnavailable with actionable message."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    provider = OllamaProvider(client=mock_client)
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "Unable to establish connection to Ollama" in exc_info.value.message
    assert exc_info.value.details["provider"] == "ollama"


@pytest.mark.unit
def test_ollama_generate_sql_timeout() -> None:
    """Verify timeout exception raises LLMUnavailable."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ReadTimeout("Read timed out")

    provider = OllamaProvider(timeout=30.0, client=mock_client)
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "timed out after 30.0s" in exc_info.value.message
    assert exc_info.value.details["timeout_seconds"] == 30.0


@pytest.mark.unit
def test_ollama_generate_sql_model_not_found_404() -> None:
    """Verify HTTP 404 returns actionable missing model message with pull command."""
    mock_client = MagicMock()
    req = httpx.Request("POST", "http://localhost:11434/api/chat")
    resp = httpx.Response(404, text='{"error":"model \'llama3.2:latest\' not found"}', request=req)
    mock_client.post.side_effect = httpx.HTTPStatusError("Not Found", request=req, response=resp)

    provider = OllamaProvider(model="llama3.2:latest", client=mock_client)
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "ollama pull llama3.2:latest" in exc_info.value.message
    assert exc_info.value.details["status_code"] == 404


@pytest.mark.unit
def test_ollama_generate_sql_upstream_http_500() -> None:
    """Verify non-404 HTTP status errors raise upstream error LLMUnavailable."""
    mock_client = MagicMock()
    req = httpx.Request("POST", "http://localhost:11434/api/chat")
    resp = httpx.Response(500, text="Internal Server Error", request=req)
    mock_client.post.side_effect = httpx.HTTPStatusError("Server Error", request=req, response=resp)

    provider = OllamaProvider(client=mock_client)
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "upstream error (500)" in exc_info.value.message


@pytest.mark.unit
def test_ollama_generate_sql_generic_exception() -> None:
    """Verify unexpected non-HTTP exceptions raise LLMUnavailable."""
    mock_client = MagicMock()
    mock_client.post.side_effect = RuntimeError("Kernel failure")

    provider = OllamaProvider(client=mock_client)
    with pytest.raises(LLMUnavailable, match="currently unavailable"):
        provider.generate_sql("Test query")


@pytest.mark.unit
def test_ollama_explain_success() -> None:
    """Verify plain English explanation is extracted from response."""
    mock_client = MagicMock()
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={
            "message": {
                "content": "Total revenue across delivered orders reached $142,500.00."
            }
        },
    )

    provider = OllamaProvider(client=mock_client)
    explanation = provider.explain(
        question="What is total revenue?",
        columns=["total_revenue"],
        rows=[[142500.0]],
        row_count=1,
    )
    assert explanation == "Total revenue across delivered orders reached $142,500.00."


@pytest.mark.unit
def test_ollama_explain_empty_content_fallback() -> None:
    """Verify empty message explanation returns deterministic row summary."""
    mock_client = MagicMock()
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={"message": {"content": "   "}},
    )

    provider = OllamaProvider(client=mock_client)
    explanation = provider.explain(
        question="List products",
        columns=["id", "name"],
        rows=[[1, "Gadget"]],
        row_count=1,
    )
    assert explanation == "Query returned 1 row(s) for id, name."


@pytest.mark.unit
def test_ollama_explain_failure_raises_llmunavailable() -> None:
    """Verify explain network failure raises LLMUnavailable."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("Ollama down")

    provider = OllamaProvider(client=mock_client)
    with pytest.raises(LLMUnavailable, match="failed to generate explanation"):
        provider.explain(
            question="What is total revenue?",
            columns=["total_revenue"],
            rows=[[100.0]],
            row_count=1,
        )


@pytest.mark.unit
def test_ollama_unsafe_sql_rejected_by_validator() -> None:
    """Verify malicious or unsafe SQL generated by Ollama is strictly rejected by the validator."""
    mock_client = MagicMock()
    # Model hallucinates or is prompted to generate DROP TABLE
    mock_client.post.return_value = _create_mock_response(
        status_code=200,
        json_data={
            "message": {
                "content": '{"supported": true, "sql": "DROP TABLE customers;"}'
            }
        },
    )

    provider = OllamaProvider(client=mock_client)
    response = run_query(
        question="Drop the customers table",
        request_id="req_test_unsafe_ollama",
        provider=provider,
        settings=Settings(),
    )

    assert response.status == "rejected"
    assert response.sql == "DROP TABLE customers;"
    assert response.rows == []
    assert len(response.rejection_reasons) > 0
    assert any("not permitted" in r.lower() or "only select" in r.lower() for r in response.rejection_reasons)


@pytest.mark.live
@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE_OLLAMA") == "1"),
    reason="Live Ollama smoke test skipped unless RUN_LIVE_OLLAMA=1",
)
def test_ollama_live_canonical_revenue() -> None:
    """Live integration smoke test verifying Ollama generates canonical revenue query (status != 'cancelled')."""
    settings = Settings(LLM_PROVIDER="ollama", LLM_MODEL="llama3.2:latest")
    provider = OllamaProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.LLM_MODEL,
        timeout=settings.OLLAMA_TIMEOUT_SECONDS,
    )
    result = provider.generate_sql("What is the total revenue across all completed orders?")
    assert result.supported is True
    assert result.sql is not None
    assert "status != 'cancelled'" in result.sql or "status <> 'cancelled'" in result.sql

