"""Ollama local LLM provider implementation with JSON-schema constrained decoding.

Communicates with a locally running Ollama instance (defaulting to llama3.2:latest)
via Ollama's REST API (/api/chat), requiring no API keys or paid external services.
"""

from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import LLMUnavailable
from app.core.logging import get_logger
from app.llm.base import SQLGeneration
from app.llm.prompts import build_system_prompt

logger = get_logger("app.llm.ollama_provider")


class OllamaProvider:
    """LLM provider communicating with local Ollama service using structured JSON schema."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings: Settings = get_settings()
        self.base_url = (base_url or self.settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or (
            "llama3.2:latest"
            if self.settings.LLM_MODEL == "claude-3-5-sonnet-20241022"
            else self.settings.LLM_MODEL
        )
        self.timeout = timeout if timeout is not None else self.settings.OLLAMA_TIMEOUT_SECONDS
        self.client = client or httpx.Client(timeout=self.timeout)

    def generate_sql(self, question: str, schema_context: str | None = None) -> SQLGeneration:
        """Translate a natural language question into SQLGeneration via Ollama /api/chat."""
        system_prompt = schema_context or build_system_prompt(self.settings)
        schema = SQLGeneration.model_json_schema()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "format": schema,
            "options": {
                "temperature": 0.0,
            },
        }

        try:
            response = self.client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout) as ex:
            logger.error("Failed to connect to Ollama at %s: %s", self.base_url, ex)
            raise LLMUnavailable(
                message=(
                    f"Unable to establish connection to Ollama at '{self.base_url}'. "
                    "Verify that the Ollama service is running."
                ),
                details={"provider": "ollama", "base_url": self.base_url},
            ) from ex
        except httpx.TimeoutException as ex:
            logger.warning("Ollama request timed out after %.1fs: %s", self.timeout, ex)
            raise LLMUnavailable(
                message=f"Ollama request timed out after {self.timeout:.1f}s.",
                details={"provider": "ollama", "timeout_seconds": self.timeout},
            ) from ex
        except httpx.HTTPStatusError as ex:
            status_code = ex.response.status_code
            error_text = ex.response.text
            logger.error("Ollama API returned HTTP %s: %s", status_code, error_text)
            if status_code == 404:
                raise LLMUnavailable(
                    message=(
                        f"Ollama model '{self.model}' was not found. "
                        f"Run 'ollama pull {self.model}' to download it."
                    ),
                    details={"provider": "ollama", "model": self.model, "status_code": 404},
                ) from ex
            raise LLMUnavailable(
                message=f"Ollama API returned upstream error ({status_code}).",
                details={"provider": "ollama", "status_code": status_code},
            ) from ex
        except Exception as ex:
            logger.exception("Unexpected exception communicating with Ollama provider: %s", ex)
            raise LLMUnavailable(
                message="LLM provider is currently unavailable.",
                details={"provider": "ollama"},
            ) from ex

        try:
            data = response.json()
            content = data.get("message", {}).get("content", "")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty or missing content in Ollama message response.")
        except Exception as ex:
            logger.error("Failed to parse Ollama response body: %s", ex)
            raise LLMUnavailable(
                message="LLM provider returned an invalid response structure.",
                details={"provider": "ollama"},
            ) from ex

        # Strip markdown fences if emitted by the model despite format constraints
        cleaned_content = content.strip()
        if cleaned_content.startswith("```"):
            lines = cleaned_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_content = "\n".join(lines).strip()

        try:
            return SQLGeneration.model_validate_json(cleaned_content)
        except Exception as ex:
            logger.error(
                "Failed validating Ollama JSON output against SQLGeneration: %s (raw content: %s)",
                ex,
                content,
            )
            raise LLMUnavailable(
                message="LLM provider returned malformed structured data.",
                details={"provider": "ollama"},
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

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        try:
            response = self.client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return content
            return f"Query returned {total_rows} row(s) for {', '.join(columns)}."
        except Exception as ex:
            logger.warning("Ollama explain() call failed: %s", ex)
            raise LLMUnavailable(
                message="LLM provider failed to generate explanation.",
                details={"provider": "ollama"},
            ) from ex
