"""Natural language analytics query endpoint."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.schemas.errors import ErrorEnvelope
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query_service import run_query

router = APIRouter(tags=["Query"])


def get_llm_provider() -> LLMProvider:
    """FastAPI dependency for injecting the configured LLMProvider."""
    return get_provider()


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=200,
    summary="Execute Natural Language Query",
    description=(
        "Translates natural language questions into safe SQL via LLMProvider, validates "
        "via SQLGlot AST policy engine, executes under the restricted dq_readonly role, "
        "and returns tabular results.\n\n"
        "The returned status is:\n"
        "- `success`: Query was translated, validated, and executed against the database.\n"
        "- `unsupported`: The question cannot be answered by the schema or is out of domain.\n"
        "- `rejected`: Generated SQL violated security policies or schema constraints.\n\n"
        "Explanations will be implemented in Phase 6 (answer=null, explanation_source='none')."
    ),
    responses={
        200: {
            "description": "Query processed (status: success, unsupported, or rejected).",
            "model": QueryResponse,
        },
        422: {
            "description": "Request validation failed (blank, too short, or too long question).",
            "model": ErrorEnvelope,
        },
        503: {
            "description": "LLM provider or database service currently unavailable.",
            "model": ErrorEnvelope,
        },
        504: {
            "description": "Database query timed out during execution.",
            "model": ErrorEnvelope,
        },
    },
)
def execute_query(
    payload: QueryRequest,
    request: Request,
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> QueryResponse:
    """Execute natural language query workflow."""
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or f"req_{uuid.uuid4().hex[:12]}"
    )
    return run_query(
        question=payload.question,
        request_id=request_id,
        provider=provider,
        include_explanation=payload.include_explanation,
    )
