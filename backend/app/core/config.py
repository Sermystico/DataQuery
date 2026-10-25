"""Core application configuration loaded via pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database Settings
    POSTGRES_DB: str = Field(default="dataquery_dev")
    POSTGRES_OWNER_USER: str = Field(default="dq_owner")
    POSTGRES_OWNER_PASSWORD: str = Field(default="dq_owner_dev_pw")
    POSTGRES_READONLY_USER: str = Field(default="dq_readonly")
    POSTGRES_READONLY_PASSWORD: str = Field(default="dq_readonly_dev_pw")
    POSTGRES_APP_USER: str = Field(default="dq_app")
    POSTGRES_APP_PASSWORD: str = Field(default="dq_app_dev_pw")
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5434)

    # LLM Settings
    LLM_PROVIDER: str = Field(default="mock")
    ANTHROPIC_API_KEY: str = Field(default="mock-dev-key")
    LLM_MODEL: str = Field(default="claude-3-5-sonnet-20241022")

    # Analytics Context Settings
    ANALYTICS_AS_OF_DATE: str = Field(default="2024-11-01T00:00:00Z")
    QUERY_TIMEOUT_MS: int = Field(default=3000)
    MAX_RESULT_ROWS: int = Field(default=100)

    # API Settings
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    @property
    def owner_database_url(self) -> str:
        """SQLAlchemy database URL for migrations and DDL as dq_owner."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_OWNER_USER}:{self.POSTGRES_OWNER_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def readonly_database_url(self) -> str:
        """SQLAlchemy database URL for analytics query execution as dq_readonly."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_READONLY_USER}:{self.POSTGRES_READONLY_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def app_database_url(self) -> str:
        """SQLAlchemy database URL for application state logging as dq_app."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_APP_USER}:{self.POSTGRES_APP_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
