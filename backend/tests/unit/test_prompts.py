"""Unit tests for system prompt construction and prompt security."""

import pytest

from app.core.config import get_settings
from app.llm.prompts import build_system_prompt
from app.security.policy import ALLOWED_TABLES


@pytest.mark.unit
def test_system_prompt_contains_mandatory_elements() -> None:
    """Verify system prompt includes as-of date, approved tables, and business rules."""
    settings = get_settings()
    prompt = build_system_prompt()

    # 1. Analytical time anchor
    assert settings.as_of_date.isoformat() in prompt
    assert "Last month" in prompt or "last month" in prompt
    assert "NEVER use dynamic clock functions" in prompt

    # 2. Approved tables
    for tbl in ALLOWED_TABLES:
        assert f"Table: {tbl}" in prompt

    # 3. Business definitions
    assert "Revenue" in prompt
    assert "Undelivered" in prompt or "undelivered" in prompt
    assert "region" in prompt.lower()

    # 4. Critical security instructions
    assert "CRITICAL SECURITY RULES" in prompt
    assert "untrusted" in prompt.lower() or "DATA" in prompt
    assert "SELECT" in prompt

    # 5. Zero secrets check
    assert settings.POSTGRES_OWNER_PASSWORD.get_secret_value() not in prompt
    assert settings.POSTGRES_READONLY_PASSWORD.get_secret_value() not in prompt
    assert settings.POSTGRES_APP_PASSWORD.get_secret_value() not in prompt
    assert settings.ANTHROPIC_API_KEY.get_secret_value() not in prompt


@pytest.mark.unit
def test_system_prompt_does_not_contain_user_question() -> None:
    """Verify build_system_prompt does not take or format user questions into the system turn."""
    prompt = build_system_prompt()
    # Ensure there is no placeholder or prompt string interpolation for user question
    assert "{question}" not in prompt
    assert "{user_question}" not in prompt
