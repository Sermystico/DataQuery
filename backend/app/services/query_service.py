"""Natural language query orchestration service for DataQuery.

Orchestrates the end-to-end analytics workflow:
1. Translates natural language into SQL via LLMProvider (or Mock).
2. Validates the generated SQL using SQLGlot AST security policies.
3. Executes validated SQL strictly within the read-only transaction under dq_readonly.
4. Formats results to JSON-safe data types and generates visualization chart hints.
5. Generates human-readable explanations strictly from returned data.
6. Records execution audit metadata in app.query_history using dq_app role.
7. Packages results into the standard QueryResponse model.
"""

import time

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.history_repo import record_query_history
from app.llm.base import LLMProvider, SQLGeneration
from app.llm.factory import get_provider
from app.schemas.query import QueryResponse
from app.security.query_executor import ExecutionResult, execute_query
from app.security.sql_validator import ValidatedSQL, ValidationResult, validate_sql
from app.services.explainer import generate_explanation
from app.services.formatter import format_result

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
    History is recorded reliably for success, unsupported, and rejected outcomes.
    """
    overall_start = time.perf_counter()

    if settings is None:
        settings = get_settings()
    if provider is None:
        provider = get_provider(settings)

    # Step 1: Generate SQL via LLM
    generation, _ = _generate_sql_step(provider, question, request_id)

    if not generation.supported:
        reason_msg = generation.reason or "The question is not supported by the database domain."
        duration_ms = (time.perf_counter() - overall_start) * 1000.0
        logger.info("[request_id=%s] Query marked unsupported: %s", request_id, reason_msg)

        history_id = record_query_history(
            request_id=request_id,
            question=question,
            status="unsupported",
            sql=None,
            row_count=None,
            error_code="UNSUPPORTED_QUESTION",
            duration_ms=duration_ms,
        )

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
            history_id=history_id,
            rejection_reasons=[reason_msg],
        )

    assert generation.sql is not None, "Supported generation must contain SQL."

    # Step 2: AST Security Validation
    validation, _ = _validate_sql_step(generation.sql, settings.MAX_RESULT_ROWS, request_id)

    if not validation.valid:
        duration_ms = (time.perf_counter() - overall_start) * 1000.0
        logger.warning(
            "[request_id=%s] Query rejected by SQL validation policy. Reasons: %s",
            request_id,
            validation.reasons,
        )

        history_id = record_query_history(
            request_id=request_id,
            question=question,
            status="rejected",
            sql=generation.sql,
            row_count=None,
            error_code="VALIDATION_REJECTED",
            duration_ms=duration_ms,
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
            history_id=history_id,
            rejection_reasons=validation.reasons,
        )

    # Step 3: Read-Only Database Execution
    assert validation.validated_sql is not None, (
        "Valid validation result must contain ValidatedSQL token."
    )
    try:
        exec_result, _ = _execute_query_step(
            validation.validated_sql,
            settings.MAX_RESULT_ROWS,
            request_id,
        )
    except AppError as exc:
        duration_ms = (time.perf_counter() - overall_start) * 1000.0
        record_query_history(
            request_id=request_id,
            question=question,
            status="error",
            sql=validation.normalized_sql,
            row_count=None,
            error_code=exc.code,
            duration_ms=duration_ms,
        )
        raise
    except Exception:
        duration_ms = (time.perf_counter() - overall_start) * 1000.0
        record_query_history(
            request_id=request_id,
            question=question,
            status="error",
            sql=validation.normalized_sql,
            row_count=None,
            error_code="INTERNAL_ERROR",
            duration_ms=duration_ms,
        )
        raise

    # Step 4: Format results to JSON-safe types and determine chart hints
    formatted_rows, chart_hint = format_result(exec_result.columns, exec_result.rows)

    # Step 5: Generate explanation from actual results
    answer, explanation_source = generate_explanation(
        question=question,
        columns=exec_result.columns,
        rows=formatted_rows,
        row_count=len(formatted_rows),
        provider=provider,
        include_explanation=include_explanation,
    )

    # Step 6: Record successful execution in history
    duration_ms = (time.perf_counter() - overall_start) * 1000.0
    history_id = record_query_history(
        request_id=request_id,
        question=question,
        status="success",
        sql=validation.normalized_sql,
        row_count=len(formatted_rows),
        error_code=None,
        duration_ms=duration_ms,
    )

    # Step 7: Return final QueryResponse
    return QueryResponse(
        status="success",
        question=question,
        answer=answer,
        sql=validation.normalized_sql,
        columns=exec_result.columns,
        rows=formatted_rows,
        row_count=len(formatted_rows),
        truncated=exec_result.truncated,
        chart_hint=chart_hint,
        explanation_source=explanation_source,
        request_id=request_id,
        history_id=history_id,
        rejection_reasons=[],
    )
