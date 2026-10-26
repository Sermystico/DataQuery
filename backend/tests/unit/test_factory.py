"""Unit tests for app/llm/factory.py provider instantiation."""

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import AppError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.factory import get_provider
from app.llm.mock_provider import MockLLMProvider


@pytest.mark.unit
def test_get_provider_mock() -> None:
    """Verify get_provider returns MockLLMProvider when configured."""
    settings = Settings(LLM_PROVIDER="mock")
    provider = get_provider(settings)
    assert isinstance(provider, MockLLMProvider)


@pytest.mark.unit
def test_get_provider_default_uses_get_settings() -> None:
    """Verify get_provider with None settings resolves successfully."""
    provider = get_provider(None)
    assert provider is not None


@pytest.mark.unit
def test_get_provider_anthropic_missing_or_placeholder_key() -> None:
    """Verify get_provider raises AppError when Anthropic key is missing or placeholder."""
    # Empty string
    empty_settings = Settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=SecretStr(""))
    with pytest.raises(AppError) as exc_info:
        get_provider(empty_settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"
    assert exc_info.value.http_status == 500

    # Placeholder string
    placeholder_settings = Settings(
        LLM_PROVIDER="anthropic",
        ANTHROPIC_API_KEY=SecretStr("your_anthropic_api_key_here"),
    )
    with pytest.raises(AppError) as exc_info:
        get_provider(placeholder_settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"


@pytest.mark.unit
def test_get_provider_anthropic_valid_key() -> None:
    """Verify get_provider constructs AnthropicProvider when valid key is provided."""
    valid_settings = Settings(
        LLM_PROVIDER="anthropic",
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test-dummy-key-for-unit-test"),
        LLM_MODEL="claude-3-5-sonnet-20241022",
    )
    provider = get_provider(valid_settings)
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-3-5-sonnet-20241022"


@pytest.mark.unit
def test_get_provider_ollama_default_model() -> None:
    """Verify get_provider constructs OllamaProvider with default model llama3.2:latest."""
    from app.llm.ollama_provider import OllamaProvider

    settings = Settings(
        LLM_PROVIDER="ollama",
        LLM_MODEL="claude-3-5-sonnet-20241022",
        OLLAMA_BASE_URL="http://localhost:11434",
    )
    provider = get_provider(settings)
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3.2:latest"
    assert provider.base_url == "http://localhost:11434"


@pytest.mark.unit
def test_get_provider_ollama_custom_model() -> None:
    """Verify get_provider preserves custom configured Ollama chat model."""
    from app.llm.ollama_provider import OllamaProvider

    settings = Settings(
        LLM_PROVIDER="ollama",
        LLM_MODEL="qwen2.5-coder:7b",
        OLLAMA_BASE_URL="http://localhost:11434",
    )
    provider = get_provider(settings)
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "qwen2.5-coder:7b"


@pytest.mark.unit
def test_get_provider_ollama_embedding_model_rejected() -> None:
    """Verify get_provider rejects nomic-embed-text embedding model with CONFIGURATION_ERROR."""
    settings = Settings(
        LLM_PROVIDER="ollama",
        LLM_MODEL="nomic-embed-text:latest",
    )
    with pytest.raises(AppError) as exc_info:
        get_provider(settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"
    assert "embedding model" in exc_info.value.message


@pytest.mark.unit
def test_get_provider_gemini_missing_or_placeholder_key() -> None:
    """Verify get_provider raises AppError when Gemini key is missing or placeholder."""
    # Empty string
    empty_settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY=SecretStr(""),
        GEMINI_MODEL="gemini-2.5-flash",
    )
    with pytest.raises(AppError) as exc_info:
        get_provider(empty_settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"
    assert "GEMINI_API_KEY" in exc_info.value.message

    # Placeholder string
    placeholder_settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY=SecretStr("your_gemini_api_key_here"),
        GEMINI_MODEL="gemini-2.5-flash",
    )
    with pytest.raises(AppError) as exc_info:
        get_provider(placeholder_settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"


@pytest.mark.unit
def test_get_provider_gemini_missing_model() -> None:
    """Verify get_provider raises AppError when Gemini model name is missing."""
    settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY=SecretStr("valid-gemini-key"),
        GEMINI_MODEL=None,
    )
    with pytest.raises(AppError) as exc_info:
        get_provider(settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"
    assert "GEMINI_MODEL" in exc_info.value.message


@pytest.mark.unit
def test_get_provider_gemini_valid_config() -> None:
    """Verify get_provider constructs GeminiProvider when valid key and model are supplied."""
    from app.llm.gemini_provider import GeminiProvider

    settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY=SecretStr("valid-test-gemini-key"),
        GEMINI_MODEL="gemini-2.5-flash",
    )
    provider = get_provider(settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-2.5-flash"


@pytest.mark.unit
def test_get_provider_unsupported_provider() -> None:
    """Verify get_provider raises AppError when provider is unknown."""
    invalid_settings = Settings(LLM_PROVIDER="openai-unknown")
    with pytest.raises(AppError) as exc_info:
        get_provider(invalid_settings)
    assert exc_info.value.code == "CONFIGURATION_ERROR"
    assert "Unsupported LLM_PROVIDER" in exc_info.value.message

