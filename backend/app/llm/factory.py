"""Factory function for instantiating the configured LLMProvider."""

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockLLMProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Return an instantiated LLMProvider based on settings.LLM_PROVIDER.

    Raises:
        AppError: If LLM_PROVIDER is unrecognized or if Anthropic is selected without a valid API key.
    """
    if settings is None:
        settings = get_settings()

    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "anthropic":
        raw_key = settings.ANTHROPIC_API_KEY.get_secret_value()
        # Ensure key is provided and not the placeholder example value
        if not raw_key or raw_key.strip() in ("", "your_anthropic_api_key_here"):
            raise AppError(
                message=(
                    "ANTHROPIC_API_KEY must be configured with a valid API key "
                    "when LLM_PROVIDER is set to 'anthropic'."
                ),
                code="CONFIGURATION_ERROR",
                http_status=500,
                details={"provider": "anthropic", "setting": "ANTHROPIC_API_KEY"},
            )
        return AnthropicProvider(api_key=raw_key, model=settings.LLM_MODEL)

    raise AppError(
        message=f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}'. Expected 'mock' or 'anthropic'.",
        code="CONFIGURATION_ERROR",
        http_status=500,
        details={"supported_providers": ["mock", "anthropic"]},
    )
