"""Unit tests for AnthropicProvider using a faked Anthropic SDK client."""

import os
from unittest.mock import MagicMock

import httpx
import pytest
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.core.errors import LLMUnavailable
from app.llm.anthropic_provider import AnthropicProvider


def _build_fake_tool_block(tool_name: str, input_dict: dict) -> MagicMock:
    """Helper to build a faked Anthropic ToolUseBlock."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = input_dict
    return block


@pytest.fixture
def fake_client() -> MagicMock:
    """Mock anthropic.Anthropic client."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = MagicMock()
    return client


@pytest.fixture
def http_req_resp() -> tuple[httpx.Request, httpx.Response]:
    """Provide dummy httpx Request and Response objects for Anthropic exception constructors."""
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(400, request=req)
    return req, resp


@pytest.mark.unit
def test_anthropic_provider_success_supported(fake_client: MagicMock) -> None:
    """Verify successful tool use extraction for supported query."""
    tool_block = _build_fake_tool_block(
        "generate_sql",
        {"supported": True, "sql": "SELECT id, name FROM customers;", "reason": None},
    )
    fake_client.messages.create.return_value = MagicMock(content=[tool_block])

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    result = provider.generate_sql("What are customer names?")

    assert result.supported is True
    assert result.sql == "SELECT id, name FROM customers;"
    assert result.reason is None
    fake_client.messages.create.assert_called_once()


@pytest.mark.unit
def test_anthropic_provider_success_unsupported(fake_client: MagicMock) -> None:
    """Verify successful tool use extraction for unsupported query."""
    tool_block = _build_fake_tool_block(
        "generate_sql",
        {"supported": False, "sql": None, "reason": "Query asks for weather forecasts."},
    )
    fake_client.messages.create.return_value = MagicMock(content=[tool_block])

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    result = provider.generate_sql("What is the weather?")

    assert result.supported is False
    assert result.sql is None
    assert result.reason == "Query asks for weather forecasts."


@pytest.mark.unit
def test_anthropic_provider_missing_tool_call_raises_unavailable(fake_client: MagicMock) -> None:
    """Verify response missing tool_use block raises LLMUnavailable."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is your query: SELECT 1"
    fake_client.messages.create.return_value = MagicMock(content=[text_block])

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="invalid response structure"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_malformed_tool_input_raises_unavailable(fake_client: MagicMock) -> None:
    """Verify invalid tool_use input schema raises LLMUnavailable."""
    # supported=True but missing sql
    tool_block = _build_fake_tool_block("generate_sql", {"supported": True, "sql": None})
    fake_client.messages.create.return_value = MagicMock(content=[tool_block])

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="malformed structured data"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_authentication_error(
    fake_client: MagicMock, http_req_resp: tuple[httpx.Request, httpx.Response]
) -> None:
    """Verify AuthenticationError is mapped to LLMUnavailable without leaking secrets."""
    _, resp = http_req_resp
    resp.status_code = 401
    fake_client.messages.create.side_effect = AuthenticationError(
        message="Invalid API Key: sk-ant-secret12345",
        response=resp,
        body=None,
    )

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="authentication failed") as exc_info:
        provider.generate_sql("What is total revenue?")

    assert "secret12345" not in str(exc_info.value.message)
    assert exc_info.value.http_status == 503


@pytest.mark.unit
def test_anthropic_provider_rate_limit_error(
    fake_client: MagicMock, http_req_resp: tuple[httpx.Request, httpx.Response]
) -> None:
    """Verify RateLimitError is mapped to LLMUnavailable."""
    _, resp = http_req_resp
    resp.status_code = 429
    fake_client.messages.create.side_effect = RateLimitError(
        message="Rate limit reached", response=resp, body=None
    )

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="rate limit exceeded"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_timeout_error(
    fake_client: MagicMock, http_req_resp: tuple[httpx.Request, httpx.Response]
) -> None:
    """Verify APITimeoutError is mapped to LLMUnavailable."""
    req, _ = http_req_resp
    fake_client.messages.create.side_effect = APITimeoutError(request=req)

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="request timed out"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_connection_error(
    fake_client: MagicMock, http_req_resp: tuple[httpx.Request, httpx.Response]
) -> None:
    """Verify APIConnectionError is mapped to LLMUnavailable."""
    req, _ = http_req_resp
    fake_client.messages.create.side_effect = APIConnectionError(request=req)

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="Unable to establish connection"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_status_error(
    fake_client: MagicMock, http_req_resp: tuple[httpx.Request, httpx.Response]
) -> None:
    """Verify APIStatusError is mapped to LLMUnavailable."""
    _, resp = http_req_resp
    resp.status_code = 502
    fake_client.messages.create.side_effect = APIStatusError(
        message="Bad Gateway", response=resp, body=None
    )

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="upstream error"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_unexpected_exception(fake_client: MagicMock) -> None:
    """Verify unexpected general exception is mapped to LLMUnavailable."""
    fake_client.messages.create.side_effect = RuntimeError("Low-level memory corruption")

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="currently unavailable"):
        provider.generate_sql("What is total revenue?")


@pytest.mark.unit
def test_anthropic_provider_explain_success() -> None:
    """Verify explain() invokes messages.create with short tokens and returns explanation text."""
    fake_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "The total revenue was $1,500."
    fake_response = MagicMock()
    fake_response.content = [mock_block]
    fake_client.messages.create.return_value = fake_response

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    res = provider.explain("What is total revenue?", ["total_revenue"], [[1500.0]], 1)

    assert res == "The total revenue was $1,500."
    fake_client.messages.create.assert_called_once()
    call_kwargs = fake_client.messages.create.call_args[1]
    assert call_kwargs["max_tokens"] <= 250
    assert "system" in call_kwargs


@pytest.mark.unit
def test_anthropic_provider_explain_failure_raises_llm_unavailable() -> None:
    """Verify explain() maps client exceptions to LLMUnavailable."""
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = Exception("Anthropic API down")

    provider = AnthropicProvider(api_key="fake-key", client=fake_client)
    with pytest.raises(LLMUnavailable, match="failed to generate explanation"):
        provider.explain("What is total revenue?", ["total_revenue"], [[1500.0]], 1)


@pytest.mark.live
@pytest.mark.skipif(
    not (os.getenv("RUN_LIVE") == "1" and os.getenv("ANTHROPIC_API_KEY")),
    reason="Live smoke test skipped unless RUN_LIVE=1 and ANTHROPIC_API_KEY is provided",
)
def test_anthropic_live_smoke() -> None:
    """Optional live smoke test against Anthropic API (skipped by default)."""
    api_key = os.environ["ANTHROPIC_API_KEY"]
    provider = AnthropicProvider(api_key=api_key)
    result = provider.generate_sql("What is the total revenue across all completed orders?")
    assert result.supported is True
    assert result.sql is not None
