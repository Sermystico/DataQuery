"""Factory function for instantiating the configured LLMProvider."""

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm.ollama_provider import OllamaProvider


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Return an instantiated LLMProvider based on settings.LLM_PROVIDER.

    Raises:
        AppError: If LLM_PROVIDER is unrecognized or if provider configuration is invalid.
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

    if provider_name == "ollama":
        model_name = settings.LLM_MODEL
        if model_name == "claude-3-5-sonnet-20241022":
            model_name = "llama3.2:latest"

        if "embed" in model_name.lower():
            raise AppError(
                message=(
                    f"'{model_name}' is an embedding model and cannot be used for text generation. "
                    "Please configure a chat model such as 'llama3.2:latest'."
                ),
                code="CONFIGURATION_ERROR",
                http_status=500,
                details={"provider": "ollama", "model": model_name},
            )

        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=model_name,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )

    if provider_name == "gemini":
        raw_key = settings.GEMINI_API_KEY.get_secret_value()
        if not raw_key or raw_key.strip() in ("", "your_gemini_api_key_here", "your-gemini-api-key-here"):
            raise AppError(
                message=(
                    "GEMINI_API_KEY must be configured with a valid API key "
                    "when LLM_PROVIDER is set to 'gemini'."
                ),
                code="CONFIGURATION_ERROR",
                http_status=500,
                details={"provider": "gemini", "setting": "GEMINI_API_KEY"},
            )
        model_name = (
            settings.effective_gemini_model
            if hasattr(settings, "effective_gemini_model")
            else settings.GEMINI_MODEL
        )
        if not model_name:
            raise AppError(
                message=(
                    "GEMINI_MODEL must be configured with a valid model name "
                    "when LLM_PROVIDER is set to 'gemini'."
                ),
                code="CONFIGURATION_ERROR",
                http_status=500,
                details={"provider": "gemini", "setting": "GEMINI_MODEL"},
            )
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=raw_key.strip(),
            model=model_name,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
        )

    raise AppError(
        message=(
            f"Unsupported LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
            "Expected 'mock', 'anthropic', 'ollama', or 'gemini'."
        ),
        code="CONFIGURATION_ERROR",
        http_status=500,
        details={"supported_providers": ["mock", "anthropic", "ollama", "gemini"]},
    )

