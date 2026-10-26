"""SQL validation API endpoint."""

from fastapi import APIRouter

from app.schemas.sql import SQLValidateRequest, SQLValidateResponse
from app.security.sql_validator import validate_sql

router = APIRouter(tags=["SQL"])


@router.post(
    "/sql/validate",
    response_model=SQLValidateResponse,
    status_code=200,
    summary="Validate SQL Syntax and Policy Compliance",
    description=(
        "Parses a raw SQL query string with SQLGlot, validates against AST security policies, "
        "checks table/column/function allowlists, and injects a row LIMIT clause. "
        "Never executes queries against the database."
    ),
    responses={
        200: {
            "description": "Validation result containing policy evaluation status and normalized SQL.",
            "model": SQLValidateResponse,
        },
    },
)
def validate_sql_endpoint(payload: SQLValidateRequest) -> SQLValidateResponse:
    """Validate raw SQL string without executing it."""
    result = validate_sql(payload.sql)
    return SQLValidateResponse(
        valid=result.valid,
        reasons=result.reasons,
        normalized_sql=result.normalized_sql,
    )
