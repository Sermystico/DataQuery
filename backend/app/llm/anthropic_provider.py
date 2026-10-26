"""Anthropic Claude LLM provider implementation with forced tool-call schema validation.

Consulted Official Anthropic Documentation:
- Tool Use / Function Calling: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- Forcing Tool Use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use#forcing-tool-use

Usage Pattern:
- Tool definition uses `SQLGeneration.model_json_schema()`.
- Forced tool execution uses `tool_choice={"type": "tool", "name": "generate_sql"}`.
- Model name dynamically retrieved from settings.LLM_MODEL.
"""

from typing import Any

import anthropic
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailable
from app.core.logging import get_logger
from app.llm.base import SQLGeneration
from app.llm.prompts import build_system_prompt

logger = get_logger("app.llm.anthropic_provider")

TOOL_NAME = "generate_sql"


class AnthropicProvider:
    """LLM provider communicating with Anthropic Claude via official Anthropic SDK."""

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.settings: Settings = get_settings()
        self.model = model or self.settings.LLM_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = client or anthropic.Anthropic(
            api_key=api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def generate_sql(self, question: str, schema_context: str | None = None) -> SQLGeneration:
        """Translate a natural language question into SQLGeneration using forced tool calling."""
        system_prompt = schema_context or build_system_prompt(self.settings)

        tools = [
            {
                "name": TOOL_NAME,
                "description": (
                    "Translate the natural language question into a PostgreSQL query if supported, "
                    "or indicate why the question is unsupported."
                ),
                "input_schema": SQLGeneration.model_json_schema(),
            }
        ]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": question}],
                tools=tools,
                tool_choice={"type": "tool", "name": TOOL_NAME},
            )
        except AuthenticationError as ex:
            logger.error("Anthropic authentication error: verify ANTHROPIC_API_KEY configuration.")
            raise LLMUnavailable(
                message="LLM provider authentication failed. Check server credentials.",
                details={"provider": "anthropic"},
            ) from ex
        except RateLimitError as ex:
            logger.warning("Anthropic rate limit exceeded for model %s.", self.model)
            raise LLMUnavailable(
                message="LLM provider rate limit exceeded. Please retry shortly.",
                details={"provider": "anthropic", "retryable": True},
            ) from ex
        except APITimeoutError as ex:
            logger.warning("Anthropic request timed out after %.1fs.", self.timeout)
            raise LLMUnavailable(
                message="LLM provider request timed out.",
                details={"provider": "anthropic", "timeout_seconds": self.timeout},
            ) from ex
        except APIConnectionError as ex:
            logger.error("Failed to connect to Anthropic API endpoints.")
            raise LLMUnavailable(
                message="Unable to establish connection to LLM provider.",
                details={"provider": "anthropic"},
            ) from ex
        except APIStatusError as ex:
            logger.error("Anthropic API returned status %s: %s", ex.status_code, ex.message)
            raise LLMUnavailable(
                message="LLM provider returned an upstream error.",
                details={"provider": "anthropic", "status_code": ex.status_code},
            ) from ex
        except Exception as ex:
            logger.exception("Unexpected exception communicating with Anthropic provider: %s", ex)
            raise LLMUnavailable(
                message="LLM provider is currently unavailable.",
                details={"provider": "anthropic"},
            ) from ex

        # Extract tool use block
        tool_call = next(
            (
                block
                for block in response.content
                if getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == TOOL_NAME
            ),
            None,
        )

        if tool_call is None:
            logger.error("Anthropic response missing mandatory '%s' tool call.", TOOL_NAME)
            raise LLMUnavailable(
                message="LLM provider returned an invalid response structure (missing tool call).",
                details={"provider": "anthropic"},
            )

        try:
            return SQLGeneration.model_validate(tool_call.input)
        except Exception as ex:
            logger.error("Failed validating tool_use input against SQLGeneration: %s", ex)
            raise LLMUnavailable(
                message="LLM provider returned malformed structured data.",
                details={"provider": "anthropic"},
            ) from ex

    def explain(
        self,
        question: str,
        columns: list[str],
        rows: list[list[Any]],
        sql: str,
    ) -> str:
        """Phase 6 placeholder for natural language explanation generation."""
        raise NotImplementedError(
            "Natural language result explanations are deferred to Phase 6 implementation."
        )
