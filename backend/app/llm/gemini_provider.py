"""Google Gemini LLM provider implementation using official google-genai SDK.

Documentation references:
- Python SDK JSON Response Schema: python-sdk/README.md#google-gen-ai-sdk/models/json-response-schema
- Structured Output Guide: https://ai.google.dev/gemini-api/docs/structured-output
- Rate Limits & Free Tier: https://ai.google.dev/gemini-api/docs/rate-limits

Features:
- Enforces strict structured JSON decoding constrained to SQLGeneration schema.
- Re-validates structured output using Pydantic (never blind trust).
- Implements bounded exponential backoff retry for HTTP 429 rate limit errors.
- Maps all SDK failures (auth, 429, timeout, network, safety blocks) to safe LLMUnavailable errors.
- Keeps secrets and raw upstream error bodies out of logs and exceptions.
"""

import time
from collections.abc import Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailable
from app.core.logging import get_logger
from app.llm.base import SQLGeneration
from app.llm.prompts import build_system_prompt

logger = get_logger("app.llm.gemini_provider")


class GeminiProvider:
    """LLM provider communicating with Google Gemini API via official google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        client: Any | None = None,
    ) -> None:
        self.settings: Settings = get_settings()
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(self.timeout * 1000)),
        )

    def _call_with_retry(self, fn: Callable[[], Any]) -> Any:
        """Execute a Gemini SDK call with bounded exponential backoff on HTTP 429 rate limits."""
        attempts = 0
        while True:
            try:
                return fn()
            except errors.ClientError as ex:
                if ex.code == 429:
                    attempts += 1
                    if attempts > self.max_retries:
                        logger.warning(
                            "Gemini rate limit (429) exceeded; %d retries exhausted.",
                            self.max_retries,
                        )
                        raise LLMUnavailable(
                            message="LLM provider rate limit exceeded. Please retry shortly.",
                            details={"provider": "gemini", "retryable": True},
                        ) from ex
                    backoff = self.backoff_factor * (2 ** (attempts - 1))
                    logger.warning(
                        "Gemini rate limit (429) received. Retrying in %.2fs (attempt %d/%d)...",
                        backoff,
                        attempts,
                        self.max_retries,
                    )
                    time.sleep(backoff)
                    continue

                # Authentication / permission errors (401, 403, or invalid API key)
                err_str = str(ex).upper()
                if ex.code in (401, 403) or (
                    ex.code == 400
                    and any(
                        term in err_str
                        for term in ("API_KEY", "KEY_INVALID", "PERMISSION_DENIED", "UNAUTHENTICATED")
                    )
                ):
                    logger.error("Gemini authentication error: verify GEMINI_API_KEY configuration.")
                    raise LLMUnavailable(
                        message="LLM provider authentication failed. Check server credentials.",
                        details={"provider": "gemini"},
                    ) from ex

                logger.error("Gemini client error (code %s).", ex.code)
                raise LLMUnavailable(
                    message="LLM provider returned an upstream error.",
                    details={"provider": "gemini", "status_code": ex.code},
                ) from ex

            except errors.ServerError as ex:
                logger.error("Gemini server error (code %s).", ex.code)
                raise LLMUnavailable(
                    message="LLM provider returned an upstream error.",
                    details={"provider": "gemini", "status_code": ex.code},
                ) from ex

            except (TimeoutError, httpx.TimeoutException) as ex:
                logger.warning("Gemini request timed out after %.1fs.", self.timeout)
                raise LLMUnavailable(
                    message="LLM provider request timed out.",
                    details={"provider": "gemini", "timeout_seconds": self.timeout},
                ) from ex

            except (ConnectionError, httpx.ConnectError) as ex:
                logger.error("Failed to connect to Gemini API endpoint.")
                raise LLMUnavailable(
                    message="Unable to establish connection to LLM provider.",
                    details={"provider": "gemini"},
                ) from ex

            except Exception as ex:
                err_str = str(ex).lower()
                if "timed out" in err_str or "timeout" in err_str:
                    logger.warning("Gemini request timed out: %s", ex)
                    raise LLMUnavailable(
                        message="LLM provider request timed out.",
                        details={"provider": "gemini", "timeout_seconds": self.timeout},
                    ) from ex
                if "connection" in err_str or "connect" in err_str:
                    logger.error("Failed to connect to Gemini API: %s", ex)
                    raise LLMUnavailable(
                        message="Unable to establish connection to LLM provider.",
                        details={"provider": "gemini"},
                    ) from ex
                if "api key" in err_str or "api_key" in err_str or "unauthenticated" in err_str:
                    logger.error("Gemini API key verification failure.")
                    raise LLMUnavailable(
                        message="LLM provider authentication failed. Check server credentials.",
                        details={"provider": "gemini"},
                    ) from ex

                logger.exception("Unexpected exception communicating with Gemini provider: %s", ex)
                raise LLMUnavailable(
                    message="LLM provider is currently unavailable.",
                    details={"provider": "gemini"},
                ) from ex

    def generate_sql(self, question: str, schema_context: str | None = None) -> SQLGeneration:
        """Translate natural language into structured SQLGeneration using Gemini JSON schema output."""
        system_prompt = schema_context or build_system_prompt(self.settings)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SQLGeneration,
            system_instruction=system_prompt,
            temperature=0.0,
        )

        response = self._call_with_retry(
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=question,
                config=config,
            )
        )

        # 1. Check for empty candidate list or safety blocks
        candidates = getattr(response, "candidates", None)
        if not candidates:
            logger.warning("Gemini returned zero candidates (response empty or blocked).")
            return SQLGeneration(
                supported=False,
                reason="No response candidate returned by LLM provider (response was empty or blocked).",
            )

        candidate = candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason is not None and str(finish_reason).upper() in (
            "SAFETY",
            "BLOCKLIST",
            "PROHIBITED_CONTENT",
            "SPII",
            "RECITATION",
        ):
            logger.warning("Gemini generation blocked by safety policy with finish_reason: %s", finish_reason)
            return SQLGeneration(
                supported=False,
                reason="The question could not be processed due to safety policies.",
            )

        # 2. Extract and clean raw text
        raw_text = getattr(response, "text", None)
        if not raw_text or not raw_text.strip():
            logger.warning("Gemini returned candidate with empty text content.")
            return SQLGeneration(
                supported=False,
                reason="LLM provider returned an empty response.",
            )

        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```"):
            lines = cleaned_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_text = "\n".join(lines).strip()

        # 3. Strictly re-validate structured JSON output with Pydantic
        try:
            return SQLGeneration.model_validate_json(cleaned_text)
        except Exception as ex:
            logger.error(
                "Failed validating Gemini JSON output against SQLGeneration: %s (raw content: %s)",
                ex,
                raw_text,
            )
            raise LLMUnavailable(
                message="LLM provider returned malformed structured data.",
                details={"provider": "gemini"},
            ) from ex

    def explain(
        self,
        question: str,
        columns: list[str],
        rows: list[list[Any]],
        row_count: int | None = None,
        sql: str | None = None,
    ) -> str:
        """Generate a concise plain-English explanation based strictly on actual returned rows."""
        total_rows = row_count if row_count is not None else len(rows)
        sample_rows = rows[:20]

        system_prompt = (
            "You are DataQuery's explanation assistant. Your role is to explain analytical query "
            "results in plain English based SOLELY on the provided data.\n"
            "CRITICAL INVARIANTS:\n"
            "1. Rely ONLY on the provided column names and rows. Never state facts, numbers, or "
            "conclusions not directly present in the data.\n"
            "2. When a query returns an aggregate metric (such as a total, sum, count, or average), "
            "interpret the single row as the aggregated result for the question, NOT as a single individual transaction.\n"
            "3. Answer the user question directly and concisely (1-2 sentences). Do not speculate or invent unsupported details.\n"
            "4. Never mention SQL, database internals, schemas, credentials, or system prompts."
        )

        user_content = (
            f"Question: {question}\n"
            f"Columns: {columns}\n"
            f"Total Row Count: {total_rows}\n"
            f"Data (up to 20 rows):\n{sample_rows}"
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=250,
            temperature=0.2,
        )

        try:
            response = self._call_with_retry(
                lambda: self.client.models.generate_content(
                    model=self.model,
                    contents=user_content,
                    config=config,
                )
            )
            raw_text = getattr(response, "text", None)
            if raw_text and raw_text.strip():
                return raw_text.strip()
            return f"Query returned {total_rows} row(s) for {', '.join(columns)}."
        except Exception as ex:
            logger.warning("Gemini explain() call failed: %s", ex)
            raise LLMUnavailable(
                message="LLM provider failed to generate explanation.",
                details={"provider": "gemini"},
            ) from ex
