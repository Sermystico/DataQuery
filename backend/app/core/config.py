"""Core application configuration loaded via pydantic-settings."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DOTENV_PATH = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_DOTENV_PATH), ".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database Settings
    POSTGRES_DB: str = "dataquery_dev"
    POSTGRES_OWNER_USER: str = "dq_owner"
    POSTGRES_OWNER_PASSWORD: SecretStr = SecretStr("dq_owner_dev_pw")
    POSTGRES_READONLY_USER: str = "dq_readonly"
    POSTGRES_READONLY_PASSWORD: SecretStr = SecretStr("dq_readonly_dev_pw")
    POSTGRES_APP_USER: str = "dq_app"
    POSTGRES_APP_PASSWORD: SecretStr = SecretStr("dq_app_dev_pw")
    DB_HOST: str = "localhost"
    DB_PORT: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL server port")

    # LLM Settings
    LLM_PROVIDER: str = "mock"
    ANTHROPIC_API_KEY: SecretStr = SecretStr("mock-dev-key")
    LLM_MODEL: str = "claude-3-5-sonnet-20241022"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT_SECONDS: float = Field(
        default=120.0, gt=0, description="Ollama request timeout in seconds"
    )
    GEMINI_API_KEY: SecretStr = SecretStr("")
    GEMINI_MODEL: str | None = Field(
        default=None, description="Gemini model identifier (must be specified via GEMINI_MODEL)"
    )
    GEMINI_TIMEOUT_SECONDS: float = Field(
        default=30.0, gt=0, description="Gemini request timeout in seconds"
    )

    # Analytics Context Settings
    ANALYTICS_AS_OF_DATE: str = "2024-11-01T00:00:00Z"
    QUERY_TIMEOUT_MS: int = Field(
        default=3000, gt=0, description="Database statement execution timeout in ms"
    )
    MAX_RESULT_ROWS: int = Field(
        default=100, gt=0, le=1000, description="Max rows returned per query"
    )

    # API Settings
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def as_of_date(self) -> date:
        """Return ANALYTICS_AS_OF_DATE parsed as a datetime.date object."""
        return date.fromisoformat(self.ANALYTICS_AS_OF_DATE.split("T")[0])

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS_ORIGINS parsed as a list of origin strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def effective_gemini_model(self) -> str | None:
        """Return configured Gemini model from GEMINI_MODEL, falling back to LLM_MODEL if it matches Gemini."""
        if self.GEMINI_MODEL and self.GEMINI_MODEL.strip():
            return self.GEMINI_MODEL.strip()
        if self.LLM_MODEL and "gemini" in self.LLM_MODEL.lower():
            return self.LLM_MODEL.strip()
        return None

    @property
    def owner_database_url(self) -> str:
        """SQLAlchemy database URL for migrations and DDL as dq_owner."""
        escaped_user = quote_plus(self.POSTGRES_OWNER_USER)
        escaped_password = quote_plus(self.POSTGRES_OWNER_PASSWORD.get_secret_value())
        return (
            f"postgresql+psycopg://{escaped_user}:{escaped_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def readonly_database_url(self) -> str:
        """SQLAlchemy database URL for analytics query execution as dq_readonly."""
        escaped_user = quote_plus(self.POSTGRES_READONLY_USER)
        escaped_password = quote_plus(self.POSTGRES_READONLY_PASSWORD.get_secret_value())
        return (
            f"postgresql+psycopg://{escaped_user}:{escaped_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def app_database_url(self) -> str:
        """SQLAlchemy database URL for application state logging as dq_app."""
        escaped_user = quote_plus(self.POSTGRES_APP_USER)
        escaped_password = quote_plus(self.POSTGRES_APP_PASSWORD.get_secret_value())
        return (
            f"postgresql+psycopg://{escaped_user}:{escaped_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
