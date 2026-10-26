"""Unit tests for application configuration, secret masking, and property parsing."""

from datetime import date

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings


@pytest.mark.unit
def test_secrets_masked_in_str_and_repr() -> None:
    """Verify passwords and API keys are SecretStr and never exposed in plaintext."""
    settings = get_settings()

    # Secret types
    assert isinstance(settings.POSTGRES_OWNER_PASSWORD, SecretStr)
    assert isinstance(settings.POSTGRES_READONLY_PASSWORD, SecretStr)
    assert isinstance(settings.POSTGRES_APP_PASSWORD, SecretStr)
    assert isinstance(settings.ANTHROPIC_API_KEY, SecretStr)

    # String representation must mask secret values
    assert str(settings.POSTGRES_OWNER_PASSWORD) == "**********"
    assert str(settings.POSTGRES_READONLY_PASSWORD) == "**********"
    assert str(settings.POSTGRES_APP_PASSWORD) == "**********"
    assert str(settings.ANTHROPIC_API_KEY) == "**********"

    # Repr of entire Settings object must not contain raw secret strings
    settings_repr = repr(settings)
    assert "dq_owner_dev_pw" not in settings_repr
    assert "dq_readonly_dev_pw" not in settings_repr
    assert "dq_app_dev_pw" not in settings_repr
    assert "mock-dev-key" not in settings_repr

    # Raw value is only exposed when explicitly calling .get_secret_value()
    assert settings.POSTGRES_OWNER_PASSWORD.get_secret_value() == "dq_owner_dev_pw"
    assert settings.POSTGRES_READONLY_PASSWORD.get_secret_value() == "dq_readonly_dev_pw"
    assert settings.POSTGRES_APP_PASSWORD.get_secret_value() == "dq_app_dev_pw"
    assert (
        settings.ANTHROPIC_API_KEY.get_secret_value() == "mock-dev-key-not-active"
        or settings.ANTHROPIC_API_KEY.get_secret_value() == "mock-dev-key"
    )


@pytest.mark.unit
def test_analytics_as_of_date_property() -> None:
    """Verify ANALYTICS_AS_OF_DATE correctly parses ISO strings into datetime.date."""
    settings = get_settings()
    assert settings.as_of_date == date(2024, 11, 1)

    # Custom override
    custom = Settings(ANALYTICS_AS_OF_DATE="2025-06-30T12:00:00Z")
    assert custom.as_of_date == date(2025, 6, 30)

    # Date-only string
    custom_date_only = Settings(ANALYTICS_AS_OF_DATE="2025-12-25")
    assert custom_date_only.as_of_date == date(2025, 12, 25)


@pytest.mark.unit
def test_cors_origins_list_property() -> None:
    """Verify CORS_ORIGINS string is cleanly parsed into a list of origins."""
    settings = get_settings()
    assert settings.cors_origins_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Custom comma-separated with arbitrary whitespace
    custom = Settings(CORS_ORIGINS="https://example.com ,  http://localhost:3000 , ")
    assert custom.cors_origins_list == [
        "https://example.com",
        "http://localhost:3000",
    ]

    # Empty string produces empty list
    empty = Settings(CORS_ORIGINS="")
    assert empty.cors_origins_list == []


@pytest.mark.unit
def test_database_url_generation_and_encoding() -> None:
    """Verify database URLs correctly format and URL-escape components."""
    settings = get_settings()
    assert settings.owner_database_url.startswith("postgresql+psycopg://dq_owner:")
    assert settings.readonly_database_url.startswith("postgresql+psycopg://dq_readonly:")
    assert settings.app_database_url.startswith("postgresql+psycopg://dq_app:")

    # Verify special characters in passwords are percent-encoded
    special_settings = Settings(
        POSTGRES_OWNER_USER="user@domain",
        POSTGRES_OWNER_PASSWORD=SecretStr("p@ss#word/123"),
        DB_HOST="localhost",
        DB_PORT=5432,
        POSTGRES_DB="test_db",
    )
    url = special_settings.owner_database_url
    assert "user%40domain" in url
    assert "p%40ss%23word%2F123" in url
    assert "@localhost:5432/test_db" in url
