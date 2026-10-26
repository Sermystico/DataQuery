"""Unit tests for GeminiProvider using a faked Gemini SDK client."""

import os
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors

from app.core.errors import LLMUnavailable
from app.llm.base import SQLGeneration
from app.llm.gemini_provider import GeminiProvider


def _make_mock_response(
    text: str = "",
    finish_reason: str = "STOP",
    has_candidate: bool = True,
) -> MagicMock:
    """Helper to build a faked Gemini GenerateContentResponse."""
    resp = MagicMock()
    resp.text = text
    if has_candidate:
        candidate = MagicMock()
        candidate.finish_reason = finish_reason
        resp.candidates = [candidate]
    else:
        resp.candidates = []
    return resp


@pytest.fixture
def fake_client() -> MagicMock:
    """Mock google.genai.Client instance."""
    client = MagicMock()
    client.models = MagicMock()
    client.models.generate_content = MagicMock()
    return client


@pytest.mark.unit
def test_gemini_provider_defaults_and_initialization() -> None:
    """Verify GeminiProvider initializes properly with parameters."""
    provider = GeminiProvider(
        api_key="test-gemini-key",
        model="gemini-2.5-flash",
        timeout=45.0,
        max_retries=3,
        backoff_factor=0.1,
    )
    assert provider.api_key == "test-gemini-key"
    assert provider.model == "gemini-2.5-flash"
    assert provider.timeout == 45.0
    assert provider.max_retries == 3
    assert provider.backoff_factor == 0.1
    assert provider.client is not None


@pytest.mark.unit
def test_gemini_generate_sql_success_supported(fake_client: MagicMock) -> None:
    """Verify successful parsing of structured JSON generation for supported query."""
    fake_client.models.generate_content.return_value = _make_mock_response(
        text='{"supported": true, "sql": "SELECT id, name FROM customers;", "reason": null}'
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    result = provider.generate_sql("List all customers")

    assert isinstance(result, SQLGeneration)
    assert result.supported is True
    assert result.sql == "SELECT id, name FROM customers;"
    assert result.reason is None
    fake_client.models.generate_content.assert_called_once()


@pytest.mark.unit
def test_gemini_generate_sql_success_unsupported(fake_client: MagicMock) -> None:
    """Verify successful parsing of unsupported question with reason."""
    fake_client.models.generate_content.return_value = _make_mock_response(
        text='{"supported": false, "sql": null, "reason": "Weather forecasts are not in the database."}'
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    result = provider.generate_sql("What is the weather in Seattle?")

    assert result.supported is False
    assert result.sql is None
    assert result.reason == "Weather forecasts are not in the database."


@pytest.mark.unit
def test_gemini_generate_sql_markdown_fences_stripped(fake_client: MagicMock) -> None:
    """Verify markdown ```json codeblock wrappers are cleanly stripped before validation."""
    fake_client.models.generate_content.return_value = _make_mock_response(
        text='```json\n{"supported": true, "sql": "SELECT COUNT(*) FROM orders;", "reason": null}\n```'
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    result = provider.generate_sql("How many orders?")

    assert result.supported is True
    assert result.sql == "SELECT COUNT(*) FROM orders;"


@pytest.mark.unit
def test_gemini_generate_sql_malformed_json(fake_client: MagicMock) -> None:
    """Verify non-JSON output raises LLMUnavailable without leaking raw content."""
    fake_client.models.generate_content.return_value = _make_mock_response(
        text="{this is not valid json}"
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "malformed structured data" in exc_info.value.message
    assert exc_info.value.details["provider"] == "gemini"


@pytest.mark.unit
def test_gemini_generate_sql_schema_violating_output(fake_client: MagicMock) -> None:
    """Verify schema-violating output (supported=True but missing SQL) raises LLMUnavailable."""
    fake_client.models.generate_content.return_value = _make_mock_response(
        text='{"supported": true, "sql": null}'
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "malformed structured data" in exc_info.value.message


@pytest.mark.unit
def test_gemini_generate_sql_empty_response(fake_client: MagicMock) -> None:
    """Verify empty response or candidates returns safe unsupported result without crashing."""
    # 1. Zero candidates
    fake_client.models.generate_content.return_value = _make_mock_response(has_candidate=False)

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    result = provider.generate_sql("Test query")
    assert result.supported is False
    assert "empty or blocked" in result.reason

    # 2. Empty text
    fake_client.models.generate_content.return_value = _make_mock_response(text="   ")
    result_empty_text = provider.generate_sql("Test query 2")
    assert result_empty_text.supported is False
    assert "empty response" in result_empty_text.reason


@pytest.mark.unit
def test_gemini_generate_sql_safety_blocked_response(fake_client: MagicMock) -> None:
    """Verify safety-blocked candidate returns safe unsupported result."""
    fake_client.models.generate_content.return_value = _make_mock_response(
        text="", finish_reason="SAFETY"
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    result = provider.generate_sql("Exploit prompt")
    assert result.supported is False
    assert "safety policies" in result.reason


@pytest.mark.unit
def test_gemini_generate_sql_invalid_key_error(fake_client: MagicMock) -> None:
    """Verify 401 or invalid API key maps to safe authentication failure LLMUnavailable."""
    fake_client.models.generate_content.side_effect = errors.ClientError(
        401, {"error": {"message": "API_KEY_INVALID", "status": "UNAUTHENTICATED"}}
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")
    assert "authentication failed" in exc_info.value.message.lower()
    assert exc_info.value.details["provider"] == "gemini"


@pytest.mark.unit
def test_gemini_generate_sql_429_retry_success(fake_client: MagicMock) -> None:
    """Verify HTTP 429 rate limit triggers bounded retry with backoff and succeeds."""
    success_resp = _make_mock_response(
        text='{"supported": true, "sql": "SELECT 1;", "reason": null}'
    )
    fake_client.models.generate_content.side_effect = [
        errors.ClientError(429, {"error": {"message": "Rate limit", "status": "RESOURCE_EXHAUSTED"}}),
        success_resp,
    ]

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        max_retries=2,
        backoff_factor=0.01,  # Fast for unit test
        client=fake_client,
    )
    result = provider.generate_sql("Test query")

    assert result.supported is True
    assert result.sql == "SELECT 1;"
    assert fake_client.models.generate_content.call_count == 2


@pytest.mark.unit
def test_gemini_generate_sql_429_exhausted(fake_client: MagicMock) -> None:
    """Verify exhausted 429 retries raises retryable LLMUnavailable."""
    fake_client.models.generate_content.side_effect = errors.ClientError(
        429, {"error": {"message": "Rate limit", "status": "RESOURCE_EXHAUSTED"}}
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        max_retries=2,
        backoff_factor=0.01,
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "rate limit exceeded" in exc_info.value.message.lower()
    assert exc_info.value.details["retryable"] is True
    assert fake_client.models.generate_content.call_count == 3  # initial + 2 retries


@pytest.mark.unit
def test_gemini_generate_sql_timeout(fake_client: MagicMock) -> None:
    """Verify timeout exception maps to LLMUnavailable with timeout details."""
    fake_client.models.generate_content.side_effect = TimeoutError("Request timed out")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        timeout=15.0,
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "timed out" in exc_info.value.message.lower()
    assert exc_info.value.details["timeout_seconds"] == 15.0


@pytest.mark.unit
def test_gemini_generate_sql_connection_error(fake_client: MagicMock) -> None:
    """Verify connection error maps to LLMUnavailable with connection message."""
    fake_client.models.generate_content.side_effect = httpx.ConnectError("Network unreachable")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "unable to establish connection" in exc_info.value.message.lower()


@pytest.mark.unit
def test_gemini_generate_sql_server_error_500(fake_client: MagicMock) -> None:
    """Verify HTTP 500 server error maps to upstream error LLMUnavailable."""
    fake_client.models.generate_content.side_effect = errors.ServerError(
        500, {"error": {"message": "Internal error", "status": "INTERNAL"}}
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "upstream error" in exc_info.value.message.lower()
    assert exc_info.value.details["status_code"] == 500


@pytest.mark.unit
def test_gemini_generate_sql_generic_exception(fake_client: MagicMock) -> None:
    """Verify unexpected exception maps to LLMUnavailable."""
    fake_client.models.generate_content.side_effect = RuntimeError("Fatal crash")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "currently unavailable" in exc_info.value.message.lower()


@pytest.mark.unit
def test_gemini_provider_client_error_bad_request(fake_client: MagicMock) -> None:
    """Verify ClientError with 400 (bad request) maps to upstream error."""
    fake_client.models.generate_content.side_effect = errors.ClientError(
        400, {"error": {"message": "Bad Request parameter invalid"}}
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "upstream error" in exc_info.value.message.lower()
    assert exc_info.value.details["status_code"] == 400


@pytest.mark.unit
def test_gemini_provider_generic_timeout_string_exception(fake_client: MagicMock) -> None:
    """Verify generic exception containing 'timed out' maps to timeout error."""
    fake_client.models.generate_content.side_effect = Exception("Read operation timed out after 30s")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "timed out" in exc_info.value.message.lower()


@pytest.mark.unit
def test_gemini_provider_generic_connection_string_exception(fake_client: MagicMock) -> None:
    """Verify generic exception containing 'connection' maps to connection error."""
    fake_client.models.generate_content.side_effect = Exception("Failed connection reset by peer")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "unable to establish connection" in exc_info.value.message.lower()


@pytest.mark.unit
def test_gemini_provider_generic_api_key_string_exception(fake_client: MagicMock) -> None:
    """Verify generic exception containing 'api key' maps to authentication error."""
    fake_client.models.generate_content.side_effect = Exception("Invalid api key provided")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.generate_sql("Test query")

    assert "authentication failed" in exc_info.value.message.lower()


@pytest.mark.unit
def test_gemini_explain_success(fake_client: MagicMock) -> None:
    """Verify explain returns plain-English text summary."""
    fake_client.models.generate_content.return_value = MagicMock(
        text="Total revenue reached $1,259,220.88 across all completed orders."
    )

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    explanation = provider.explain(
        question="What is total revenue?",
        columns=["total_revenue"],
        rows=[[1259220.88]],
        row_count=1,
    )

    assert explanation == "Total revenue reached $1,259,220.88 across all completed orders."


@pytest.mark.unit
def test_gemini_explain_empty_content_fallback(fake_client: MagicMock) -> None:
    """Verify empty text response in explain falls back to deterministic summary."""
    fake_client.models.generate_content.return_value = MagicMock(text="   ")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    explanation = provider.explain(
        question="Count customers",
        columns=["count"],
        rows=[[100]],
        row_count=1,
    )

    assert explanation == "Query returned 1 row(s) for count."


@pytest.mark.unit
def test_gemini_explain_failure_raises_llmunavailable(fake_client: MagicMock) -> None:
    """Verify explain network failure raises LLMUnavailable."""
    fake_client.models.generate_content.side_effect = httpx.ConnectError("Connection dropped")

    provider = GeminiProvider(
        api_key="fake-key",
        model="gemini-2.5-flash",
        client=fake_client,
    )
    with pytest.raises(LLMUnavailable) as exc_info:
        provider.explain(
            question="Count customers",
            columns=["count"],
            rows=[[100]],
            row_count=1,
        )
    assert "failed to generate explanation" in exc_info.value.message.lower()


@pytest.mark.live
@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE") == "1" and os.getenv("GEMINI_API_KEY")),
    reason="Live Gemini smoke test skipped unless RUN_LIVE=1 and GEMINI_API_KEY is provided",
)
def test_gemini_live_smoke() -> None:
    """Optional live smoke test against Google Gemini API (skipped by default)."""
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    provider = GeminiProvider(api_key=api_key, model=model)
    result = provider.generate_sql("What is the total revenue across all completed orders?")
    assert result.supported is True
    assert result.sql is not None
