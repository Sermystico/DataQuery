"""Natural language query orchestration service for DataQuery.

Orchestrates the end-to-end analytics workflow:
1. Translates natural language into SQL via LLMProvider (or Mock).
2. Validates the generated SQL using SQLGlot AST security policies.
3. Executes validated SQL strictly within the read-only transaction under dq_readonly.
4. Packages results into the standard QueryResponse model.
"""

import time

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider, SQLGeneration
from app.llm.factory import get_provider
from app.schemas.query import QueryResponse
from app.security.query_executor import ExecutionResult, execute_query
from app.security.sql_validator import ValidatedSQL, ValidationResult, validate_sql

logger = get_logger("app.services.query_service")


def _generate_sql_step(
    provider: LLMProvider,
    question: str,
    request_id: str,
) -> tuple[SQLGeneration, float]:
    """Execute LLM translation step with latency measurement."""
    start = time.perf_counter()
    generation = provider.generate_sql(question)
    duration_ms = (time.perf_counter() - start) * 1000.0

    logger.info(
        "[request_id=%s] Step 1: SQL generation completed in %.2fms (supported=%s)",
        request_id,
        duration_ms,
        generation.supported,
    )
    return generation, duration_ms


def _validate_sql_step(
    sql: str,
    max_rows: int,
    request_id: str,
) -> tuple[ValidationResult, float]:
    """Execute AST validation step with latency measurement."""
    start = time.perf_counter()
    validation = validate_sql(sql, max_rows=max_rows)
    duration_ms = (time.perf_counter() - start) * 1000.0

    logger.info(
        "[request_id=%s] Step 2: SQL validation completed in %.2fms (valid=%s)",
        request_id,
        duration_ms,
        validation.valid,
    )
    return validation, duration_ms


def _execute_query_step(
    validated_sql: ValidatedSQL,
    max_rows: int,
    request_id: str,
) -> tuple[ExecutionResult, float]:
    """Execute validated query step with latency measurement."""
    start = time.perf_counter()
    result = execute_query(validated_sql, max_rows=max_rows)
    duration_ms = (time.perf_counter() - start) * 1000.0

    logger.info(
        "[request_id=%s] Step 3: SQL execution completed in %.2fms (rows=%d, truncated=%s)",
        request_id,
        duration_ms,
        len(result.rows),
        result.truncated,
    )
    return result, duration_ms


def run_query(
    question: str,
    request_id: str,
    provider: LLMProvider | None = None,
    settings: Settings | None = None,
    include_explanation: bool = True,
) -> QueryResponse:
    """Orchestrate the full natural language query workflow.

    Never executes queries that fail security validation or are marked unsupported.
    """
    if settings is None:
        settings = get_settings()
    if provider is None:
        provider = get_provider(settings)

    # Step 1: Generate SQL via LLM
    generation, _ = _generate_sql_step(provider, question, request_id)

    if not generation.supported:
        reason_msg = generation.reason or "The question is not supported by the database domain."
        logger.info("[request_id=%s] Query marked unsupported: %s", request_id, reason_msg)
        return QueryResponse(
            status="unsupported",
            question=question,
            answer=None,
            sql=None,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            chart_hint=None,
            explanation_source="none",
            request_id=request_id,
            rejection_reasons=[reason_msg],
        )

    assert generation.sql is not None, "Supported generation must contain SQL."

    # Step 2: AST Security Validation
    validation, _ = _validate_sql_step(generation.sql, settings.MAX_RESULT_ROWS, request_id)

    if not validation.valid:
        logger.warning(
            "[request_id=%s] Query rejected by SQL validation policy. Reasons: %s",
            request_id,
            validation.reasons,
        )
        return QueryResponse(
            status="rejected",
            question=question,
            answer=None,
            sql=generation.sql,
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            chart_hint=None,
            explanation_source="none",
            request_id=request_id,
            rejection_reasons=validation.reasons,
        )

    # Step 3: Read-Only Database Execution
    # Only ValidatedSQL is accepted by execute_query
    assert validation.validated_sql is not None, "Valid validation result must contain ValidatedSQL token."
    exec_result, _ = _execute_query_step(
        validation.validated_sql,
        settings.MAX_RESULT_ROWS,
        request_id,
    )

    # Step 4: Assemble Final Response (Explanations deferred to Phase 6)
    return QueryResponse(
        status="success",
        question=question,
        answer=None,  # Implemented in Phase 6
        sql=validation.normalized_sql,
        columns=exec_result.columns,
        rows=exec_result.rows,
        row_count=len(exec_result.rows),
        truncated=exec_result.truncated,
        chart_hint=None,  # Implemented in Phase 6
        explanation_source="none",  # Implemented in Phase 6
        request_id=request_id,
        rejection_reasons=[],
    )
